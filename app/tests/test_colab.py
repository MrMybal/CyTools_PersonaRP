"""The Colab project: built without any model, the Tool reading its models and writing its
tasks where it is told, the verified copy of the weights, and the reading of task folders.

Nothing here downloads a model or needs a GPU; tests/acceptance runs on Colab itself cover
the rest (see app/colab/LISEZ-MOI.md for what was and was not executed).
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'colab'))

import build_colab                                                     # noqa: E402
import personarp_colab as runner                                       # noqa: E402

PYTHON = sys.executable


def _run_python(code, **environment):
    finished = subprocess.run([PYTHON, '-c', code], capture_output=True, text=True,
                              cwd=str(APP), env={**os.environ, **environment})
    assert finished.returncode == 0, finished.stderr[-2000:]
    return finished.stdout.strip()


# ------------------------------------------------------------------- relocatable folders

def test_models_and_tasks_can_live_elsewhere(tmp_path):
    shown = _run_python(
        'from personarp import paths, batches; from personarp.voice import catalog;'
        'print(paths.MODELS); print(batches.BATCHES);'
        'print(catalog.directory("qwen3tts-1.7b-base"))',
        PERSONARP_MODELS_DIR=str(tmp_path / 'drive' / 'modeles'),
        PERSONARP_BATCHES_DIR=str(tmp_path / 'drive' / 'resultats')).splitlines()
    assert Path(shown[0]) == tmp_path / 'drive' / 'modeles'
    assert Path(shown[1]) == tmp_path / 'drive' / 'resultats'
    assert Path(shown[2]).is_relative_to(tmp_path / 'drive' / 'modeles')


def test_a_relative_location_is_ignored():
    shown = _run_python('from personarp import paths; print(paths.MODELS)',
                        PERSONARP_MODELS_DIR='modeles')
    assert Path(shown) == APP.parent / 'data' / 'models'


# ------------------------------------------------------------------- copying the weights

def _model(folder, files):
    info = {'directory': 'tts/fake', 'files': []}
    for name, payload in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        info['files'].append({'name': name, 'size': len(payload),
                              'sha256': hashlib.sha256(payload).hexdigest() if len(payload) > 4
                              else ''})
    return info


def test_a_model_is_copied_with_its_receipts_and_verified(tmp_path):
    source = tmp_path / 'local'
    info = _model(source, {'model.safetensors': b'weights' * 100, 'config.json': b'{}',
                           'speech_tokenizer/model.safetensors': b'codec' * 50})
    (source / 'model.safetensors.installed.json').write_text('{"actualSha256": "x"}')
    ok, reason = runner.copy_model(source, tmp_path / 'drive', info)
    assert ok, reason
    assert (tmp_path / 'drive' / 'speech_tokenizer' / 'model.safetensors').is_file()
    assert (tmp_path / 'drive' / 'model.safetensors.installed.json').is_file()
    assert not list((tmp_path / 'drive').rglob('*.part'))


def test_a_damaged_copy_is_detected(tmp_path):
    info = _model(tmp_path / 'local', {'model.safetensors': b'weights' * 100})
    target = tmp_path / 'drive'
    target.mkdir()
    (target / 'model.safetensors').write_bytes(b'weightz' * 100)            # same size
    ok, reason = runner.verify_model(target, info)
    assert not ok and 'SHA-256 faux' in reason
    assert runner.verify_model(target, info, hashes=False)[0]              # size alone passes
    (target / 'model.safetensors').write_bytes(b'short')
    assert runner.verify_model(target, info, hashes=False) == (False,
                                                           'taille fausse : model.safetensors')


# ------------------------------------------------------------------------ task folders

def test_task_folders_are_read_with_their_characters_and_settings(tmp_path):
    places = runner.Places(tmp_path / 'projet', tmp_path / 'local')
    good = places.tasks / 'scene-1'
    (good / 'personnages').mkdir(parents=True)
    (good / 'liste.csv').write_text('id;personnage;texte\nA;Maëlis;Oui.\n', encoding='utf-8')
    (good / 'personnages' / 'valdrenn.zip').write_bytes(b'zip')
    (good / 'tache.json').write_text(json.dumps({'langue': 'English', 'taille_lot': 8,
                                                 'bibliotheque': True}), encoding='utf-8')
    (places.tasks / 'vide').mkdir()
    double = places.tasks / 'double'
    double.mkdir()
    (double / 'a.csv').write_text('x')
    (double / 'b.txt').write_text('y')
    (places.tasks / '_brouillon').mkdir()

    tasks = {task['name']: task for task in runner.find_tasks(places)}
    assert sorted(tasks) == ['double', 'scene-1', 'vide']
    assert tasks['scene-1']['problem'] == '' and tasks['scene-1']['list'].endswith('liste.csv')
    assert tasks['scene-1']['personas'] == [str(good / 'personnages' / 'valdrenn.zip')]
    assert 'aucune liste' in tasks['vide']['problem']
    assert 'plusieurs listes' in tasks['double']['problem']

    parameters = runner.task_parameters(tasks['scene-1'], 'float16')
    assert parameters['language'] == 'English' and parameters['batch_size'] == 8
    assert parameters['use_library'] is True and parameters['precision'] == 'float16'
    assert parameters['name'] == 'scene-1'


def test_a_task_uses_only_its_own_characters_by_default(tmp_path):
    places = runner.Places(tmp_path / 'projet', tmp_path / 'local')
    (places.tasks / 't').mkdir(parents=True)
    (places.tasks / 't' / 'liste.txt').write_text('Maëlis: Oui.', encoding='utf-8')
    parameters = runner.task_parameters(runner.find_tasks(places)[0], 'auto')
    assert parameters['use_library'] is False and parameters['batch_size'] == 0


# --------------------------------------------------------------------- the project itself

@pytest.fixture(scope='module')
def project(tmp_path_factory):
    return build_colab.build(tmp_path_factory.mktemp('colab') / 'CyTools_PersonaRP_Colab')


def test_the_project_carries_no_model_and_no_window(project):
    files = [path for path in project.rglob('*') if path.is_file()]
    assert not [path for path in files
                if path.suffix in ('.safetensors', '.bin', '.pt', '.gguf', '.onnx')]
    app = project / 'outil' / 'app'
    assert (app / 'tool.py').is_file() and (app / 'setup_engine.py').is_file()
    assert (app / 'workers' / 'tts_worker.py').is_file()
    assert not (app / 'gui').exists() and not (app / 'desktop.py').exists()
    assert not (app / 'tests').exists()
    assert not list(project.rglob('*.whl'))                   # the SDK comes from GitHub
    assert (project / 'taches' / 'exemple-valdrenn' / 'personnages' / 'valdrenn.zip').is_file()
    version = json.loads((project / 'outil' / 'VERSION.json').read_text(encoding='utf-8'))
    assert version['tool'] == 'cy.tool.personarp' and 'none' in version['models']
    assert version['sdk'].startswith('cytools-core[mcp] @ git+https://github.com/MrMybal/CyToolsCore.git@')


def test_the_notebook_runs_the_runner_step_by_step(project):
    notebook = json.loads((project / 'PersonaRP_Colab.ipynb').read_text(encoding='utf-8'))
    sources = [''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code']
    steps = [command for command in ('installer', 'modeles', 'essai', 'taches', 'lancer', 'etat')
             if any('personarp_colab.py' in source and ' ' + command in source
                    for source in sources)]
    assert steps == ['installer', 'modeles', 'essai', 'taches', 'lancer', 'etat']
    assert "J_ACCEPTE_LES_LICENCES = False" in sources[0]                  # never pre-accepted
    assert 'drive.mount' in sources[1]


def test_the_built_tool_starts_without_window_or_audio_libraries(project, tmp_path):
    code = ('import sys\n'
            'for name in ("imgui_bundle", "sounddevice", "win32crypt", "win32api"):\n'
            '    sys.modules[name] = None\n'
            'sys.path.insert(0, sys.argv[1])\n'
            'import tool\n'
            'with tool.create_runtime(sys.argv[2]) as runtime:\n'
            '    names = {op["id"] for op in runtime.descriptor["operations"]}\n'
            '    print("speak_batch_file" in names and "install_voice_model" in names)\n')
    finished = subprocess.run([PYTHON, '-c', code, str(project / 'outil' / 'app'),
                               str(tmp_path / 'jobs')], capture_output=True, text=True)
    assert finished.returncode == 0, finished.stderr[-2000:]
    assert finished.stdout.strip() == 'True'


def test_building_again_keeps_tasks_models_and_results(project):
    (project / 'resultats' / 'garde.txt').write_text('x')
    (project / 'modeles' / 'garde.txt').write_text('x')
    (project / 'taches' / 'exemple-valdrenn' / 'liste.csv').write_text('modifiée', encoding='utf-8')
    build_colab.build(project)
    assert (project / 'resultats' / 'garde.txt').is_file()
    assert (project / 'modeles' / 'garde.txt').is_file()
    assert (project / 'taches' / 'exemple-valdrenn' / 'liste.csv').read_text(
        encoding='utf-8') == 'modifiée'


def test_each_command_leaves_a_journal_and_the_report_gathers_it(project, tmp_path):
    """What a real session did is kept on Drive, and one file carries it back."""
    runner = [PYTHON, str(project / 'personarp_colab.py'), '--projet', str(project),
              '--local', str(tmp_path / 'local')]
    first = subprocess.run(runner + ['etat'], capture_output=True, text=True, encoding='utf-8')
    assert first.returncode == 0, first.stderr[-2000:]
    failing = subprocess.run(runner + ['essai'], capture_output=True, text=True, encoding='utf-8')
    assert failing.returncode != 0                    # no engine on this disk: recorded as such
    journal = json.loads((project / 'resultats' / 'journal-colab.json').read_text(encoding='utf-8'))
    assert [entry['command'] for entry in journal[-2:]] == ['etat', 'essai']
    assert journal[-2]['ok'] and not journal[-1]['ok'] and journal[-1]['error']
    assert any('GPU' in line for line in journal[-2]['lines'])
    made = subprocess.run(runner + ['rapport'], capture_output=True, text=True, encoding='utf-8')
    assert made.returncode == 0, made.stderr[-2000:]
    [report] = sorted((project / 'resultats').glob('rapport-colab-*.json'))[-1:]
    document = json.loads(report.read_text(encoding='utf-8'))
    assert document['journal'][-1]['command'] == 'essai' and 'modelsOnDrive' in document
    assert 'token' not in report.read_text(encoding='utf-8').lower()


def test_the_project_carries_the_licences(project):
    root = APP.parent
    assert (project / 'LICENSE').read_bytes() == (root / 'LICENSE').read_bytes()
    for name in ('CyToolsCore-MIT.txt', 'SOURCES.txt'):
        assert (project / 'LICENCES' / name).read_bytes() == (root / 'LICENCES' / name).read_bytes()
    assert (project / 'outil' / 'app' / 'LICENSE-CyToolsCore.txt').is_file()
