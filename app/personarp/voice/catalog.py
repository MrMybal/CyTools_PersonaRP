"""Voice models: catalogue, installation state, download, and the private voice engine.

Weights live under data/models/tts and data/models/stt with a receipt next to each file.
A receipt carries the URL, the pinned revision, the size and the digest, and nothing about
where it sits on disk — which is what let the whole model tree be relocated.

Not every file the hub publishes comes with a SHA-256. Where one exists it is checked;
where it does not, the size is checked and the model is reported as verified *by size*
rather than pretending to a digest that was never published.
"""
import json
import shutil
from pathlib import Path

from cytools_core import CyToolError
from cytools_core.downloads import DownloadManager

from ..models import sha
from ..paths import APP, DATA, MODELS, ROOT, SETTINGS, read_json, write_json

CATALOG = APP / 'tts-catalog.json'
ENGINE = 'voice'


def catalog():
    return read_json(CATALOG)


def entry(model):
    info = catalog().get(model)
    if not info:
        raise CyToolError('NotFound', 'Unknown voice model: ' + str(model))
    return info


def directory(model):
    relative = entry(model)['directory']
    path = (MODELS / relative).resolve()
    if not path.is_relative_to(MODELS.resolve()):
        raise CyToolError('InvalidParameters', 'Model directory escapes data/models.')
    return path


def installed(model, verify=False, context=None):
    info = catalog().get(model)
    if not info:
        return False
    root = directory(model)
    for item in info['files']:
        path = root / item['name']
        if not path.is_file() or path.stat().st_size != item['size']:
            return False
        digest = item.get('sha256') or ''
        if digest:
            receipt = read_json(path.with_name(path.name + '.installed.json'))
            if receipt.get('actualSha256') and receipt['actualSha256'] != digest:
                return False
            if verify and sha(path, context) != digest:
                return False
    return True


def present_bytes(model):
    root = directory(model)
    total = 0
    for item in entry(model)['files']:
        path = root / item['name']
        if path.is_file():
            total += path.stat().st_size
    return total


def status(model, verify=False, context=None):
    info = entry(model)
    hashed = sum(1 for item in info['files'] if item.get('sha256'))
    return {
        'id': model, 'name': info['name'], 'backend': info['backend'], 'kind': info['kind'],
        'installed': installed(model, verify, context),
        'sizeBytes': sum(item['size'] for item in info['files']),
        'presentBytes': present_bytes(model), 'license': info.get('license', ''),
        'source': info.get('page', ''), 'revision': info.get('revision', ''),
        'ramGiB': info.get('ramGiB', 8), 'vramGiB': info.get('vramGiB', 6),
        'notes': info.get('notes', ''), 'directory': str(directory(model)),
        'hashedFiles': hashed, 'totalFiles': len(info['files']),
        'verification': 'sha256' if hashed == len(info['files'])
                        else ('size + sha256 where published' if hashed else 'size only'),
        'licenseAccepted': bool(read_json(SETTINGS / ('license-voice-' + model + '.json'))
                                .get('accepted')),
    }


def catalog_status(verify=False, context=None):
    return [status(model, verify, context) for model in catalog()]


def install(context, parameters):
    model = parameters['model']
    info = entry(model)
    if not parameters.get('accept_license'):
        raise CyToolError('LicenseAcceptanceRequired',
                          'Accept the model licence personally before downloading.',
                          details={'model': model, 'license': info.get('license', ''),
                                   'source': info.get('page', '')})
    root = directory(model)
    total = sum(item['size'] for item in info['files'])
    MODELS.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(MODELS).free             # where the weights go
    if free < total - present_bytes(model):
        raise CyToolError('InsufficientDisk',
                          'Not enough free space: %.1f GB needed, %.1f GB available.'
                          % (total / 1e9, free / 1e9))
    done = 0
    for item in info['files']:
        target = root / item['name']
        target.parent.mkdir(parents=True, exist_ok=True)
        DownloadManager(target.parent).download(
            target.name,
            'https://huggingface.co/%s/resolve/%s/%s' % (info['repo'], info['revision'], item['name']),
            sha256=item.get('sha256') or None, size=item['size'], revision=info['revision'],
            cancellation=context.cancellation,
            progress=lambda n, t, base=done: context.progress(
                min(99, 100 * (base + n) / total), currentStep='Downloading ' + info['name']))
        done += item['size']
    if not installed(model, True, context):
        raise CyToolError('IntegrityFailure', 'Voice model verification failed after download.')
    write_json(SETTINGS / ('license-voice-' + model + '.json'),
               {'accepted': True, 'license': info.get('license', ''), 'revision': info['revision']})
    return {'model': model, 'installed': True, 'sizeBytes': total}


def installation_resources(model):
    info = catalog().get(model, {})
    size = sum(item['size'] for item in info.get('files', []))
    return {'ramBytes': 256 * 1024 ** 2, 'cpuThreads': 1, 'diskBytes': size + 2 * 1024 ** 3}


def remove(model):
    """Delete the files of one voice model. Only ever called from an explicit request."""
    root = directory(model)
    if not root.is_dir():
        return {'model': model, 'removed': False}
    shutil.rmtree(root)
    return {'model': model, 'removed': True}


# ---------------------------------------------------------------------- engine

def engine_spec():
    return json.loads((APP / 'engines.json').read_text('utf-8-sig'))['engines'][ENGINE]


def engine_root():
    return ROOT / engine_spec()['directory']


def engine_python():
    import os
    root = engine_root()
    return root / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def engine_status():
    import sys
    sys.path.insert(0, str(APP))
    import setup_engine
    return setup_engine.status(ENGINE)


def engine_ready():
    return bool(engine_status().get('installed')) and engine_python().is_file()


def install_engine(context, parameters):
    """Create or repair the private voice environment, then import-check it."""
    import subprocess
    import sys
    command = [str(sys.executable), str(APP / 'setup_engine.py'), ENGINE]
    if parameters.get('cpu_only'):
        command.append('--cpu-only')
    context.progress(2, currentStep='Creating the private voice environment')
    log = context.path('outputs/setup-engine.log')
    with log.open('w', encoding='utf-8', errors='replace') as handle:
        process = subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                   errors='replace', bufsize=1,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                                   if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        steps = 0
        try:
            for line in process.stdout:
                handle.write(line)
                handle.flush()
                if line.startswith('[setup_engine]'):
                    steps += 1
                    context.progress(min(95, 2 + steps * 4), currentStep=line.strip()[:160])
                context.cancellation.check()
        except BaseException:
            process.kill()
            process.wait()
            raise
        code = process.wait()
    if code != 0:
        raise CyToolError('InstallationFailed',
                          'The voice engine could not be installed. See outputs/setup-engine.log.',
                          details={'log': str(log)})
    context.progress(100, currentStep='Voice engine ready')
    return {'installed': True, 'log': str(log), **engine_status()}
