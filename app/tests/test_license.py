"""PersonaRP is GPL-3.0-only; the CyToolsCore SDK it is built on is MIT, and its full text
travels with the Tool wherever the Tool goes."""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))


def _text(path):
    return Path(path).read_text(encoding='utf-8')


def test_the_tool_licence_text_is_the_gpl_3():
    text = _text(ROOT / 'LICENSE')
    assert text.startswith('                    GNU GENERAL PUBLIC LICENSE\n')
    assert 'Version 3, 29 June 2007' in text[:200] and '\r\n' not in text


def test_the_sdk_is_declared_mit_and_the_tool_gpl_3_only():
    manifest = json.loads(_text(APP / 'CyTool.json'))
    assert manifest['license'] == 'GPL-3.0-only'
    assert manifest['homepage'] == 'https://github.com/MrMybal/CyTools_PersonaRP'
    entries = {entry['kind']: entry for entry in json.loads(_text(APP / 'licenses.json'))}
    assert entries['Tool']['license'] == 'GPL-3.0-only'
    assert entries['SDK']['license'] == 'MIT' and entries['SDK']['name'] == 'CyToolsCore 0.10.1'


def test_licences_holds_the_full_mit_text_of_the_sdk_and_its_sources():
    core = _text(ROOT / 'LICENCES' / 'CyToolsCore-MIT.txt')
    assert core.startswith('MIT License\n') and 'Copyright (c) 2026 Cyberalien' in core
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in core
    assert _text(APP / 'LICENSE-CyToolsCore.txt') == core           # the scaffold's notice
    sources = _text(ROOT / 'LICENCES' / 'SOURCES.txt')
    for needed in ('https://github.com/MrMybal/CyToolsCore', 'https://github.com/MrMybal/CyTools_PersonaRP',
                   'CyToolsCore-MIT.txt', 'Python-Runtime-Notices.txt', 'GPL-3.0-only'):
        assert needed in sources, needed


def test_the_installed_sdk_is_the_pinned_mit_release():
    import importlib.metadata as metadata
    requirement = _text(APP / 'requirements.txt')
    pinned = requirement.split('CyToolsCore.git@')[1].split()[0]
    distribution = metadata.distribution('cytools-core')
    assert distribution.metadata.get('License-Expression') == 'MIT'
    assert distribution.version == '0.10.1'
    origin = json.loads(distribution.read_text('direct_url.json') or '{}')
    assert origin.get('vcs_info', {}).get('commit_id') == pinned
    assert pinned in _text(ROOT / 'LICENCES' / 'SOURCES.txt')


def test_the_copies_carried_elsewhere_have_their_licences():
    """The ComfyUI nodes and the Colab project leave this folder: they take the licences along."""
    assert _text(APP / 'comfyui' / 'cytools_personarp' / 'LICENSE') == _text(ROOT / 'LICENSE')
    builder = _text(APP / 'build_colab.py')
    assert "ROOT / 'LICENSE'" in builder and "ROOT / 'LICENCES'" in builder
    assert "'LICENCES' / 'Python-Runtime-Notices.txt'" in _text(APP / 'build_release.py')
