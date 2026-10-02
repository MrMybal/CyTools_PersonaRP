"""CyTools PersonaRP on Google Colab: voice batch tasks, with the models and the results on Drive.

The project folder lives on Google Drive and holds no model. Everything is done from the
command line, one command per step:

    python personarp_colab.py installer   copy the Tool to the Colab disk, install its
                                          light environment and its voice engine
    python personarp_colab.py modeles     download the voice models with the Tool itself
                                          (tool.py invoke install_voice_model), copy them to
                                          Drive, verify the copy, drop the local one
    python personarp_colab.py essai       one line on this card: checks the engine and
                                          chooses the precision (float16 falls back to float32)
    python personarp_colab.py taches      read every task in taches/ and check it (nothing
                                          generated)
    python personarp_colab.py lancer      run the tasks; results written on Drive as they come,
                                          an interrupted task resumes where it stopped
    python personarp_colab.py etat        what is installed, on Drive, and done

The Tool reads its models from Drive and writes its tasks there through two environment
variables it understands: PERSONARP_MODELS_DIR and PERSONARP_BATCHES_DIR.

Layout on Drive (the project folder):

    personarp_colab.py, PersonaRP_Colab.ipynb, LISEZ-MOI.md
    outil/app                    the Tool, code only (its SDK, CyToolsCore, is installed from GitHub)
    taches/<name>/               one task: its list (.csv, .txt or .json), personnages/ with
                                 the bundles exported by PersonaRP, and optionally tache.json
    modeles/                     the voice weights, filled by `modeles`
    resultats/                   one folder per task, and _taches.json (what is done)

Standard library only: it runs before anything is installed.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import wave
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LOCAL = '/content/PersonaRP'
DEFAULT_MODELS = ['qwen3tts-1.7b-base']
LIST_SUFFIXES = ('.csv', '.tsv', '.txt', '.json')
TOOL_PACKAGES = ['numpy', 'soundfile', 'Pillow', 'gguf']
STATE = '_taches.json'


SAID = []                     # what this command printed, for the journal


def say(message=''):
    print(message, flush=True)
    SAID.append(str(message))
    del SAID[:-80]


JOURNAL = 'journal-colab.json'


def gpu_name():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,compute_cap',
                               '--format=csv,noheader'], capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def record(places, command, arguments, began, code, error=''):
    """One entry per command, on Drive: what ran on which card, how long, and how it ended."""
    path = places.results / JOURNAL
    try:
        entries = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
    except ValueError:
        entries = []
    entries.append({'command': command, 'arguments': arguments,
                    'started': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(began)),
                    'seconds': round(time.time() - began, 1), 'exitCode': code, 'ok': code == 0,
                    'error': error[-2000:], 'gpu': gpu_name(), 'lines': SAID[-40:]})
    places.results.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries[-200:], ensure_ascii=False, indent=1), encoding='utf-8')


def report(places):
    """Everything a session left, in one file on Drive, to send back as it is."""
    journal = places.results / JOURNAL
    entries = json.loads(journal.read_text(encoding='utf-8')) if journal.is_file() else []
    engine = {}
    if places.engine_python().exists():
        probe = subprocess.run([str(places.engine_python()), '-c',
                                'import json, torch, platform; print(json.dumps({"torch": '
                                'torch.__version__, "cuda": torch.cuda.is_available(), "python": '
                                'platform.python_version()}))'],
                               capture_output=True, text=True, timeout=300)
        try:
            engine = json.loads(probe.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            engine = {'error': (probe.stderr or '')[-500:]}
    catalog = places.catalog()
    models = {key: verify_model(places.models / info['directory'], info, hashes=False)[0]
              for key, info in catalog.items()}
    free = shutil.disk_usage(str(places.local if places.local.exists() else '/')).free
    document = {'made': time.strftime('%Y-%m-%d %H:%M:%S'), 'platform': platform.platform(),
                'python': platform.python_version(), 'gpu': gpu_name(), 'engine': engine,
                'modelsOnDrive': models, 'precision': places.precision(),
                'freeLocalBytes': free, 'journal': entries}
    target = places.results / ('rapport-colab-%s.json' % time.strftime('%Y%m%d-%H%M%S'))
    target.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding='utf-8')
    failed = [entry['command'] for entry in entries if not entry.get('ok')]
    say('Rapport écrit : %s' % target)
    say('%d commande(s) au journal, %d en échec%s.' % (
        len(entries), len(failed), (' : ' + ', '.join(failed)) if failed else ''))
    say('Envoyez ce fichier tel quel : il ne contient ni jeton, ni modèle, ni voix.')


# ------------------------------------------------------------------------- places

class Places:
    """Where everything is: the project on Drive, and the working copy on the Colab disk."""

    def __init__(self, project, local):
        self.project = Path(project).resolve()
        self.local = Path(local)
        self.app = self.local / 'app'
        self.data = self.local / 'data'
        self.jobs = self.data / 'jobs'
        self.settings = self.data / 'settings'
        self.models = self.project / 'modeles'
        self.results = self.project / 'resultats'
        self.tasks = self.project / 'taches'
        self.local_models = self.data / 'models'

    def tool_python(self):
        return sys.executable

    def engine_python(self):
        root = self.local / 'runtime' / 'engines' / 'voice'
        return root / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

    def environment(self, models=None):
        """The Tool's environment: models and results on Drive unless told otherwise."""
        environment = dict(os.environ)
        environment['PERSONARP_MODELS_DIR'] = str(models or self.models)
        environment['PERSONARP_BATCHES_DIR'] = str(self.results)
        environment['PYTHONUTF8'] = '1'
        environment['PYTHONIOENCODING'] = 'utf-8'
        return environment

    def catalog(self):
        source = self.app / 'tts-catalog.json'
        if not source.is_file():
            source = self.project / 'outil' / 'app' / 'tts-catalog.json'
        return json.loads(source.read_text(encoding='utf-8-sig'))

    def precision(self):
        return (read_json(self.settings / 'colab.json') or {}).get('precision', 'auto')


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def run(command, **kwargs):
    say('$ ' + ' '.join(str(part) for part in command))
    return subprocess.run([str(part) for part in command], check=True, **kwargs)


# ---------------------------------------------------------------------- installer

def install(places, cpu_only=False, skip_engine=False):
    """Copy the Tool to the Colab disk and install what it needs. Nothing goes to Drive."""
    started = time.monotonic()
    source = places.project / 'outil'
    if not (source / 'app' / 'tool.py').is_file():
        raise SystemExit("Pas d'outil dans %s : le dossier du projet est incomplet." % source)
    places.local.mkdir(parents=True, exist_ok=True)
    # The code is replaced; data/ and runtime/ (the engine) are kept between two installs.
    if places.app.exists():
        shutil.rmtree(places.app)
    shutil.copytree(source / 'app', places.app,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    packages = places.local / 'packages'
    if packages.exists():
        shutil.rmtree(packages)
    if (source / 'packages').is_dir():
        shutil.copytree(source / 'packages', packages)
    else:
        packages.mkdir(parents=True)
    say('Code copié dans %s' % places.local)

    # CyToolsCore is public: the commit app/requirements.txt pins, cloned by pip.
    sdk = next(line for line in (places.app / 'requirements.txt').read_text(encoding='utf-8')
               .splitlines() if line.startswith('cytools-core'))
    run([places.tool_python(), '-m', 'pip', 'install', '--quiet', sdk] + TOOL_PACKAGES)

    if not skip_engine:
        engine = places.engine_python()
        if not engine.exists() and not _venv_works():
            # Some images ship Python without ensurepip; virtualenv does not need it.
            run([places.tool_python(), '-m', 'pip', 'install', '--quiet', 'virtualenv'])
            run([places.tool_python(), '-m', 'virtualenv', str(engine.parent.parent)])
        command = [places.tool_python(), str(places.app / 'setup_engine.py'), 'voice']
        if cpu_only:
            command.append('--cpu-only')
        run(command, cwd=str(places.local))
    say('Installé en %.0f s.' % (time.monotonic() - started))


def _venv_works():
    probe = Path('/tmp' if os.name != 'nt' else os.environ.get('TEMP', '.')) / 'personarp-venv-probe'
    shutil.rmtree(probe, ignore_errors=True)
    try:
        subprocess.run([sys.executable, '-m', 'venv', str(probe)], check=True,
                       capture_output=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


# ------------------------------------------------------------------------ modeles

def digest(path):
    hasher = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def verify_model(root, info, hashes=True):
    """(ok, reason): every file of the model present at its size, and at its digest where the
    hub publishes one."""
    for item in info['files']:
        path = Path(root) / item['name']
        if not path.is_file():
            return False, 'absent : ' + item['name']
        if path.stat().st_size != item['size']:
            return False, 'taille fausse : ' + item['name']
        if hashes and item.get('sha256') and digest(path) != item['sha256']:
            return False, 'SHA-256 faux : ' + item['name']
    return True, ''


def copy_model(source, target, info):
    """Copy one model's files and receipts to `target`, then verify the copy there."""
    target.mkdir(parents=True, exist_ok=True)
    names = [item['name'] for item in info['files']]
    names += [path.name for path in Path(source).glob('*.installed.json')]
    for name in names:
        origin = Path(source) / name
        if not origin.is_file():
            continue
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + '.part')
        shutil.copyfile(origin, partial)
        os.replace(partial, destination)
    return verify_model(target, info)


def _client_token(places):
    """A client of the local Tool allowed to download. The token never reaches the screen,
    the command line or Drive: it is kept on the Colab disk and passed by environment."""
    stored = places.settings / 'colab-client.json'
    record = read_json(stored)
    if record and record.get('token'):
        return record['token']
    places.jobs.mkdir(parents=True, exist_ok=True)
    finished = subprocess.run(
        [places.tool_python(), str(places.app / 'tool.py'), '--data-dir', str(places.jobs),
         'create-client', '--name', 'colab', '--permission', 'network',
         '--permission', 'filesystemExternal'],
        capture_output=True, text=True, cwd=str(places.local),
        env=places.environment(models=places.local_models))
    if finished.returncode != 0:
        raise SystemExit("L'outil n'a pas pu créer son client :\n" + finished.stderr[-2000:])
    token = json.loads(finished.stdout.strip().splitlines()[-1])['token']
    write_json(stored, {'token': token})
    try:
        os.chmod(stored, 0o600)
    except OSError:
        pass
    return token


def _folder_bytes(folder):
    return sum(path.stat().st_size for path in Path(folder).rglob('*') if path.is_file())


def download_with_tool(places, key, info, accept):
    """tool.py invoke install_voice_model, the Tool's own download: pinned revision, sizes
    and digests checked, licence accepted explicitly. Into the Colab disk."""
    parameters = places.settings / ('install-%s.json' % key)
    write_json(parameters, {'model': key, 'accept_license': bool(accept)})
    environment = places.environment(models=places.local_models)
    environment['CYTOOLS_TOKEN'] = _client_token(places)
    root = places.local_models / info['directory']
    total = sum(item['size'] for item in info['files'])
    done = threading.Event()

    def heartbeat():
        while not done.wait(10):
            present = _folder_bytes(root) if root.is_dir() else 0
            say('  %s: %.2f / %.2f GB' % (key, present / 1e9, total / 1e9))

    watcher = threading.Thread(target=heartbeat, daemon=True)
    watcher.start()
    try:
        finished = subprocess.run(
            [places.tool_python(), str(places.app / 'tool.py'), '--data-dir', str(places.jobs),
             'invoke', 'install_voice_model', '--params-file', str(parameters),
             '--timeout', '14400'],
            capture_output=True, text=True, cwd=str(places.local), env=environment)
    finally:
        done.set()
    if finished.returncode == 0:
        return json.loads(finished.stdout.strip().splitlines()[-1])
    text = (finished.stdout or '') + (finished.stderr or '')
    job = None
    for line in reversed(text.strip().splitlines()):
        try:
            job = json.loads(line)
            break
        except ValueError:
            continue
    error = (job or {}).get('error') or {}
    if error.get('code') == 'LicenseAcceptanceRequired':
        details = error.get('details') or {}
        raise SystemExit(
            'Licence à accepter pour %s : %s (%s).\nLisez-la, puis relancez avec '
            '--accepter-licences (dans le notebook : J_ACCEPTE_LES_LICENCES = True).'
            % (key, details.get('license') or info.get('license', ''),
               details.get('source') or info.get('page', '')))
    raise SystemExit('Le téléchargement de %s a échoué :\n%s' % (key, text[-3000:]))


def models(places, wanted, accept, keep_local=False):
    catalog = places.catalog()
    unknown = [key for key in wanted if key not in catalog]
    if unknown:
        raise SystemExit('Modèles inconnus : %s. Connus : %s'
                         % (', '.join(unknown), ', '.join(catalog)))
    places.models.mkdir(parents=True, exist_ok=True)
    for key in wanted:
        info = catalog[key]
        on_drive = places.models / info['directory']
        ok, _ = verify_model(on_drive, info, hashes=False)
        if ok:
            say('%s : déjà sur Drive (%s).' % (key, on_drive))
            continue
        say("%s : téléchargement par l'outil (%.2f Go, licence %s, %s)"
            % (key, sum(item['size'] for item in info['files']) / 1e9, info.get('license', '?'),
               info.get('page', '')))
        started = time.monotonic()
        local = places.local_models / info['directory']
        ok, _ = verify_model(local, info, hashes=False)
        if not ok:
            download_with_tool(places, key, info, accept)
        say("  téléchargé et vérifié par l'outil en %.0f s ; copie vers Drive..."
            % (time.monotonic() - started))
        started = time.monotonic()
        ok, reason = copy_model(local, on_drive, info)
        if not ok:
            raise SystemExit("La copie de %s sur Drive n'est pas bonne (%s) ; la copie locale "
                             'est gardée.' % (key, reason))
        say('  sur Drive, vérifié par taille et SHA-256, en %.0f s : %s'
            % (time.monotonic() - started, on_drive))
        if not keep_local:
            shutil.rmtree(local, ignore_errors=True)
    say("L'outil lira ses modèles dans %s" % places.models)


# ---------------------------------------------------------------------- the Tool

class Tool:
    """The Tool in this process, reading its models from Drive and writing its tasks there."""

    def __init__(self, places):
        self.places = places
        os.environ.update({key: value for key, value in places.environment().items()
                           if key.startswith(('PERSONARP_', 'PYTHON'))})
        if str(places.app) not in sys.path:
            sys.path.insert(0, str(places.app))
        from tool import create_runtime                           # after the environment
        places.jobs.mkdir(parents=True, exist_ok=True)
        self.runtime = create_runtime(str(places.jobs))
        self.runtime.__enter__()
        client = self.runtime.create_client('colab-tasks', ['filesystemExternal'])
        self.actor = self.runtime.authenticate(client['token'])
        self.session = self.runtime.create_session(self.actor, temporary=False)['sessionId']

    def close(self):
        self.runtime.__exit__(None, None, None)

    def call(self, operation, parameters, show=True):
        """Submit, show the progress on one line, return the finished job."""
        job = self.runtime.submit(self.actor, self.session, operation, parameters)
        last = ''
        try:
            while True:
                job = self.runtime.get_job(self.actor, job['jobId'])
                if job['state'] in ('Completed', 'Failed', 'Cancelled'):
                    break
                progress = job.get('progress') or {}
                line = '  %5.1f %%  %s  %s' % (progress.get('percent', 0),
                                               progress.get('currentStep', ''),
                                               progress.get('message', ''))
                if show and line != last:
                    say(line)
                    last = line
                time.sleep(2)
        except KeyboardInterrupt:
            say("Arrêt : la tâche est annulée ; ce qui est écrit reste, « lancer » la reprendra.")
            self.runtime.cancel(self.actor, job['jobId'])
            self.runtime.wait(self.actor, job['jobId'], timeout=120)
            raise
        return job


# ------------------------------------------------------------------------- tasks

def find_tasks(places):
    """Every task folder: its list, its character bundles and its settings."""
    tasks = []
    if not places.tasks.is_dir():
        return tasks
    for folder in sorted(path for path in places.tasks.iterdir() if path.is_dir()):
        if folder.name.startswith(('.', '_')):
            continue
        lists = sorted(path for path in folder.iterdir()
                       if path.is_file() and path.suffix.lower() in LIST_SUFFIXES
                       and path.name != 'tache.json')
        bundles = sorted(str(path) for path in (folder / 'personnages').glob('*')
                         if path.suffix.lower() in ('.zip', '.json')) \
            if (folder / 'personnages').is_dir() else []
        settings = read_json(folder / 'tache.json') or {}
        tasks.append({'name': folder.name, 'folder': str(folder),
                      'list': str(lists[0]) if len(lists) == 1 else '',
                      'problem': '' if len(lists) == 1 else (
                          'aucune liste (.csv, .txt ou .json) dans le dossier' if not lists else
                          'plusieurs listes dans le dossier : %s' % ', '.join(p.name for p in lists)),
                      'personas': bundles, 'settings': settings})
    return tasks


def task_parameters(task, precision):
    settings = task['settings']
    return {'file': task['list'], 'personas': task['personas'],
            'name': settings.get('nom') or task['name'],
            'use_library': bool(settings.get('bibliotheque', False)),
            'language': settings.get('langue', ''),
            'batch_size': int(settings.get('taille_lot', 0)),
            'seed': int(settings.get('graine', 42)),
            'precision': settings.get('precision') or precision,
            'device': settings.get('appareil', 'cuda')}


# The model each mode needs on Colab, named the way the `modeles` step takes it.
MODEL_FOR_MODE = {'clone': 'qwen3tts-1.7b-base', 'design': 'qwen3tts-1.7b-voicedesign',
                  'custom': 'qwen3tts-1.7b-customvoice'}


def report_errors(lines):
    """The lines that cannot be spoken, grouped by reason; a missing model says which one."""
    reasons = {}
    for line in lines:
        reasons.setdefault(line.get('error', ''), []).append(line.get('id') or str(line['index']))
    for reason, ids in reasons.items():
        shown = ', '.join(ids[:6]) + (' …' if len(ids) > 6 else '')
        missing = next((key for mode, key in MODEL_FOR_MODE.items()
                        if reason.startswith('No installed speech model can %s ' % mode)), '')
        if missing:
            say('  ! %d réplique(s) sans modèle (%s) : ajoutez %s à MODELES, étape 4 '
                '(--modele %s).' % (len(ids), shown, missing, missing))
        else:
            say('  ! %d réplique(s) (%s) : %s' % (len(ids), shown, reason))


def check_tasks(places):
    tasks = find_tasks(places)
    if not tasks:
        say('Aucune tâche dans %s. Une tâche est un dossier qui contient sa liste et, dans '
            'personnages/, les personnages exportés par PersonaRP.' % places.tasks)
        return []
    tool = Tool(places)
    reports = []
    try:
        for task in tasks:
            say('')
            say('== %s' % task['name'])
            if task['problem']:
                say('  illisible : ' + task['problem'])
                reports.append({'task': task['name'], 'ok': False})
                continue
            job = tool.call('speak_batch_file',
                            {**task_parameters(task, places.precision()), 'dry_run': True},
                            show=False)
            if job['state'] != 'Completed':
                say('  vérification en échec : %s' % json.dumps(job.get('error'), ensure_ascii=False))
                reports.append({'task': task['name'], 'ok': False})
                continue
            outputs = job['outputs']
            say('  %d réplique(s) : %d prête(s), %d impossible(s) ; personnages de la tâche : %s'
                % (outputs['lines'], outputs['ready'], outputs['failed'],
                   ', '.join(item['name'] for item in outputs['personas']) or 'aucun'))
            for group in outputs['groups']:
                say('  %-8s %-28s %d réplique(s)' % (group['mode'], group['model'], group['lines']))
            for problem in outputs['problems']:
                say('  ! ' + problem)
            report_errors([line for line in outputs['preview'] if line['status'] == 'error'])
            reports.append({'task': task['name'], 'ok': outputs['failed'] == 0, **{
                key: outputs[key] for key in ('lines', 'ready', 'failed', 'groups')}})
    finally:
        tool.close()
    return reports


def run_tasks(places, only=None):
    tasks = [task for task in find_tasks(places) if not only or task['name'] in only]
    state_path = places.results / STATE
    state = read_json(state_path) or {}
    tool = Tool(places)
    summary = []
    try:
        for task in tasks:
            say('')
            say('== %s' % task['name'])
            if task['problem']:
                say('  ignorée : ' + task['problem'])
                continue
            known = state.get(task['name']) or {}
            if known.get('complete'):
                say('  déjà faite : %s' % known.get('folder', ''))
                continue
            started = time.monotonic()
            if known.get('batch') and (places.results / known['batch'] / 'lot.json').is_file():
                say('  reprise de %s' % known['batch'])
                parameters = {'resume': known['batch'], 'precision': places.precision(),
                              'batch_size': int(task['settings'].get('taille_lot', 0))}
                job = tool.call('speak_batch', parameters)
            else:
                job = tool.call('speak_batch_file', task_parameters(task, places.precision()))
            if job['state'] != 'Completed':
                say('  en échec : %s' % json.dumps(job.get('error'), ensure_ascii=False))
                continue
            outputs = job['outputs']
            state[task['name']] = {'batch': outputs['batch'], 'folder': outputs['folder'],
                                   'complete': outputs['failed'] == 0
                                   and outputs['done'] == outputs['lines'],
                                   'done': outputs['done'], 'failed': outputs['failed'],
                                   'lines': outputs['lines'],
                                   'updated': time.strftime('%Y-%m-%d %H:%M:%S')}
            write_json(state_path, state)
            seconds = time.monotonic() - started
            say('  %d/%d réplique(s) écrite(s), %d en échec, %d déjà faite(s), en %.0f s -> %s'
                % (outputs['done'], outputs['lines'], outputs['failed'], outputs['skipped'],
                   seconds, outputs['folder']))
            for group in outputs['groups']:
                say('  %-8s lots %s, %s, pic %.1f Go'
                    % (group.get('mode'), group.get('batchSizes'), group.get('precision'),
                       (group.get('vramPeakBytes') or 0) / 1024 ** 3))
            report_errors(outputs['errors'])
            summary.append({'task': task['name'], **state[task['name']]})
    finally:
        tool.close()
    return summary


# -------------------------------------------------------------------------- essai

def loudness(path):
    with wave.open(str(path), 'rb') as handle:
        frames = handle.readframes(handle.getnframes())
        rate = handle.getframerate()
    samples = array('h', frames)
    if not samples:
        return 0.0, 0.0
    rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5 / 32768.0
    return len(samples) / rate, rms


def trial(places, precision='auto'):
    """One line spoken on this card with a voice of the example, to prove the engine and to
    choose a precision that really works here. The result is not kept on Drive."""
    bundle = places.app / 'examples' / '01-valdrenn.zip'
    line = 'ESSAI | Maëlis: Le col est fermé depuis trois jours. Personne ne monte plus.'
    tool = Tool(places)
    import personarp.batches as batches                        # imported by Tool()
    batches.BATCHES = places.data / 'essais'                    # a trial stays on the Colab disk
    chosen = None
    try:
        candidates = [precision] if precision != 'auto' else ['auto', 'float32']
        for candidate in candidates:
            started = time.monotonic()
            job = tool.call('speak_batch_file', {
                'text': line, 'personas': [str(bundle)], 'use_library': False,
                'precision': candidate, 'name': 'essai'})
            if job['state'] != 'Completed' or not job['outputs']['done']:
                say('  %s : échec : %s' % (candidate, json.dumps(
                    job.get('error') or job['outputs'].get('errors'), ensure_ascii=False)))
                continue
            outputs = job['outputs']
            group = outputs['groups'][0]
            take = Path(outputs['folder']) / 'voix' / 'ESSAI.wav'
            seconds, rms = loudness(take)
            good = seconds >= 1.5 and 0.005 <= rms <= 0.5
            say('  %s -> %s : %.1f s de parole, niveau %.3f, %.0f s chargement compris : %s'
                % (candidate, group.get('precision'), seconds, rms, time.monotonic() - started,
                   'bon' if good else 'INUTILISABLE'))
            if good:
                chosen = group.get('precision')
                break
    finally:
        tool.close()
    if not chosen:
        raise SystemExit("Aucune précision n'a donné une prise utilisable sur cette carte ; "
                         'voir les messages ci-dessus.')
    write_json(places.settings / 'colab.json', {'precision': chosen,
                                                'checked': time.strftime('%Y-%m-%d %H:%M:%S')})
    say('Précision retenue pour les tâches de cette session : %s' % chosen)
    return chosen


# -------------------------------------------------------------------------- etat

def status(places):
    try:
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,compute_cap',
                              '--format=csv,noheader'], capture_output=True, text=True).stdout.strip()
    except OSError:
        gpu = ''
    say('GPU : %s' % (gpu or 'aucun (le processeur est très lent pour les voix)'))
    say("Outil sur le disque Colab : %s" % ('oui' if (places.app / 'tool.py').is_file()
                                            else 'non -> installer'))
    say('Moteur de voix : %s' % ('oui' if places.engine_python().exists() else 'non -> installer'))
    say('Précision : %s' % places.precision())
    catalog = places.catalog()
    for key, info in catalog.items():
        ok, reason = verify_model(places.models / info['directory'], info, hashes=False)
        say('  %-28s %s' % (key, 'sur Drive' if ok else '-'))
    state = read_json(places.results / STATE) or {}
    for task in find_tasks(places):
        known = state.get(task['name']) or {}
        say('  tâche %-24s %s' % (task['name'], 'faite (%d répliques)' % known['lines']
                                  if known.get('complete') else
                                  ('%d/%d, à reprendre' % (known.get('done', 0), known.get('lines', 0))
                                   if known else 'pas commencée')))


# --------------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(
        description='CyTools PersonaRP sur Colab : tâches de voix, modèles et résultats sur Drive.')
    parser.add_argument('--projet', default=str(HERE), help='le dossier du projet sur Drive')
    parser.add_argument('--local', default=os.environ.get('PERSONARP_LOCAL', DEFAULT_LOCAL),
                        help='la copie de travail sur le disque Colab')
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('installer')
    command.add_argument('--cpu', action='store_true', help='moteur sur processeur (sans GPU)')
    command.add_argument('--sans-moteur', action='store_true', help="l'outil seul")
    command = commands.add_parser('modeles')
    command.add_argument('--modele', action='append', default=[],
                         help='identifiant du catalogue ; à répéter (par défaut : 1.7B Base)')
    command.add_argument('--accepter-licences', action='store_true',
                         help='vous avez lu les licences et les acceptez')
    command.add_argument('--garder-local', action='store_true')
    command = commands.add_parser('essai')
    command.add_argument('--precision', default='auto',
                         choices=['auto', 'bfloat16', 'float16', 'float32'])
    commands.add_parser('taches')
    command = commands.add_parser('lancer')
    command.add_argument('--tache', action='append', default=[])
    commands.add_parser('etat')
    commands.add_parser('rapport')
    arguments = parser.parse_args(argv)
    places = Places(arguments.projet, arguments.local)
    if arguments.command == 'rapport':
        report(places)
        return 0
    began, shown = time.time(), {key: value for key, value in vars(arguments).items()
                                 if key not in ('projet', 'local', 'command')}
    try:
        code = dispatch(places, arguments)
    except SystemExit as stop:
        code = stop.code if isinstance(stop.code, int) else 1
        record(places, arguments.command, shown, began, code, str(stop.code or ''))
        raise
    except BaseException as exc:
        import traceback
        record(places, arguments.command, shown, began, 1, traceback.format_exc())
        raise
    record(places, arguments.command, shown, began, code)
    return code


def dispatch(places, arguments):
    if arguments.command == 'installer':
        install(places, cpu_only=arguments.cpu, skip_engine=arguments.sans_moteur)
    elif arguments.command == 'modeles':
        models(places, arguments.modele or DEFAULT_MODELS, arguments.accepter_licences,
               keep_local=arguments.garder_local)
    elif arguments.command == 'essai':
        trial(places, arguments.precision)
    elif arguments.command == 'taches':
        reports = check_tasks(places)
        return 0 if reports and all(report['ok'] for report in reports) else 1
    elif arguments.command == 'lancer':
        try:
            run_tasks(places, arguments.tache or None)
        except KeyboardInterrupt:
            return 130
    elif arguments.command == 'etat':
        status(places)
    return 0


if __name__ == '__main__':
    sys.exit(main())
