"""The ComfyUI nodes: installed by the Tool, found where ComfyUI keeps them, and independent of
the Tool's Python.

No ComfyUI and no model here. A real ComfyUI running a workflow of these nodes is recorded in
data/reports/VALIDATION.md.
"""
import ast
import importlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import tool                                                              # noqa: E402
from personarp import comfyui                                            # noqa: E402

PACK = APP / 'comfyui' / 'cytools_personarp'


def _run(runtime, operation, parameters, permissions=('filesystemExternal',)):
    actor = runtime.authenticate(runtime.create_client('Test', list(permissions))['token'])
    session = runtime.create_session(actor, temporary=True)['sessionId']
    job = runtime.submit(actor, session, operation, parameters)
    return runtime.wait(actor, job['jobId'], timeout=60)


@pytest.fixture()
def comfy(tmp_path):
    (tmp_path / 'ComfyUI' / 'custom_nodes').mkdir(parents=True)
    return tmp_path / 'ComfyUI'


def test_a_comfyui_is_recognised_however_it_is_given(comfy, tmp_path):
    nodes = comfy / 'custom_nodes'
    assert comfyui.custom_nodes(comfy) == nodes
    assert comfyui.custom_nodes(nodes) == nodes
    assert comfyui.custom_nodes(tmp_path) == nodes                  # a portable layout
    with pytest.raises(Exception):
        comfyui.custom_nodes(tmp_path / 'nowhere')
    with pytest.raises(Exception):
        comfyui.custom_nodes('relative/path')


def test_installing_copies_the_nodes_and_names_the_tool(comfy):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'install_comfyui_nodes', {'comfyui_path': str(comfy), 'port': 8800})
        assert result['state'] == 'Completed', result.get('error')
        target = Path(result['outputs']['folder'])
        assert target == comfy / 'custom_nodes' / 'cytools_personarp'
        for name in ('__init__.py', 'client.py', 'nodes.py', 'LISEZ-MOI.md'):
            assert (target / name).is_file(), name
        config = json.loads((target / 'config.json').read_text(encoding='utf-8'))
        assert config['tool_root'] == str(APP.parent) and config['port'] == 8800
        assert not list(target.rglob('__pycache__'))
        status = _run(runtime, 'comfyui_nodes_status', {'comfyui_path': str(comfy)})['outputs']
        given = status['comfyui'][0]
        assert given['installed'] and given['upToDate']

        (target / 'nodes.py').write_text('# changed', encoding='utf-8')
        stale = _run(runtime, 'comfyui_nodes_status', {'comfyui_path': str(comfy)})['outputs']
        assert not stale['comfyui'][0]['upToDate']
        _run(runtime, 'install_comfyui_nodes', {'comfyui_path': str(comfy)})
        assert 'NODE_CLASS_MAPPINGS' in (target / 'nodes.py').read_text(encoding='utf-8')
        assert not list((comfy / 'custom_nodes').glob('.cytools_personarp-installing'))


def test_installing_needs_the_permission_and_touches_nothing_else(comfy):
    other = comfy / 'custom_nodes' / 'someone-else'
    other.mkdir()
    (other / '__init__.py').write_text('x')
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        refused = None
        try:
            _run(runtime, 'install_comfyui_nodes', {'comfyui_path': str(comfy)}, permissions=())
        except Exception as exc:                                      # noqa: BLE001
            refused = exc
        assert refused is not None and getattr(refused, 'code', '') == 'AccessDenied'
        _run(runtime, 'install_comfyui_nodes', {'comfyui_path': str(comfy)})
    assert (other / '__init__.py').read_text() == 'x'


def test_comfy_desktop_installations_are_found(tmp_path, monkeypatch):
    base = tmp_path / 'ComfyUI-base'
    (base / 'custom_nodes').mkdir(parents=True)
    config = tmp_path / 'appdata' / 'Comfy Desktop' / 'installations.json'
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps([
        {'name': 'Principal', 'adoptedBaseDir': str(base), 'adoptedPythonPath': 'py.exe'},
        {'name': 'Cassé', 'basePath': str(tmp_path / 'gone')}]), encoding='utf-8')
    monkeypatch.setenv('APPDATA', str(tmp_path / 'appdata'))
    found = comfyui.candidates()
    assert [entry['path'] for entry in found] == [str(base)]
    assert found[0]['name'] == 'Principal' and found[0]['python'] == 'py.exe'


def test_the_node_names_are_read_without_importing_the_nodes():
    names = {entry['id']: entry['name'] for entry in comfyui.node_names()}
    assert names['PersonaRP_Voice'] == 'Voix (PersonaRP)'
    assert len(names) == 8


def test_the_nodes_never_import_the_tool():
    """ComfyUI keeps its own Python: the pack talks to the Tool, it does not load it."""
    for path in PACK.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert not (node.module or '').startswith(('personarp', 'tool', 'cytools_core')), path
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(('personarp', 'tool', 'cytools_core')), path


@pytest.fixture()
def pack(monkeypatch):
    monkeypatch.syspath_prepend(str(PACK.parent))
    for name in [name for name in sys.modules if name.startswith('cytools_personarp')]:
        monkeypatch.delitem(sys.modules, name)
    module = importlib.import_module('cytools_personarp.nodes')
    return module


def test_labels_carry_the_identifier(pack):
    assert pack.identifier('Maëlis de Corvanne [maelis-de-corvanne]') == 'maelis-de-corvanne'
    assert pack.identifier('(aucun)') == ''
    assert pack.persona_of('X [x]', ' y ') == 'y'
    assert pack._always_again(seed=-1) != pack._always_again(seed=-1)   # NaN: always run again
    assert pack._always_again(seed=5) == ''


def test_menus_come_from_the_tool_files_when_it_is_not_running(pack, monkeypatch, tmp_path):
    root = tmp_path / 'PersonaRP'
    (root / 'app').mkdir(parents=True)
    (root / 'app' / 'tool.py').write_text('')
    (root / 'data' / 'personas').mkdir(parents=True)
    (root / 'data' / 'personas' / 'maelis.json').write_text(
        json.dumps({'id': 'maelis', 'name': 'Maëlis'}), encoding='utf-8')
    (root / 'data' / 'voices').mkdir()
    (root / 'app' / 'llm-catalog.json').write_text(json.dumps({
        'nymphaea': {'name': 'N'}, 'qwen25-vl-7b': {'name': 'V', 'vision': True}}))
    monkeypatch.setenv('PERSONARP_TOOL_ROOT', str(root))
    monkeypatch.setattr(pack.CLIENT, 'running', lambda: False)
    started = []
    monkeypatch.setattr(pack.CLIENT, 'ensure', lambda: started.append(True))
    pack._cache.clear()
    assert pack.characters() == ['Maëlis [maelis]']
    assert pack.voices() == [pack.NONE]
    assert pack.llm_models() == [pack.SHEET, 'nymphaea', 'qwen25-vl-7b']
    assert pack.vision_models() == [pack.SHEET, 'qwen25-vl-7b']
    assert started == []                                      # opening ComfyUI starts nothing


def test_a_wav_becomes_comfyui_audio(pack, tmp_path):
    torch = pytest.importorskip('torch')
    import struct
    import wave
    path = tmp_path / 'take.wav'
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(struct.pack('<4h', 0, 16384, -16384, 32767))
    audio = pack.audio_from_wav(path)
    assert audio['sample_rate'] == 24000 and tuple(audio['waveform'].shape) == (1, 1, 4)
    assert torch.allclose(audio['waveform'][0, 0, :2], torch.tensor([0.0, 0.5]))
    joined = pack.join_audio([path, path], gap=0.001)
    assert joined['waveform'].shape[2] == 4 + 24 + 4
