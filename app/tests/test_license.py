"""PersonaRP is GPL-3.0-only, like CyToolsCore, and says so the same way everywhere."""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))


def _licence(path):
    return Path(path).read_text(encoding='utf-8')


def test_the_licence_text_is_the_gpl_3():
    text = _licence(ROOT / 'LICENSE')
    assert text.startswith('                    GNU GENERAL PUBLIC LICENSE\n')
    assert 'Version 3, 29 June 2007' in text[:200] and '\r\n' not in text


def test_every_declaration_says_gpl_3_only():
    manifest = json.loads(_licence(APP / 'CyTool.json'))
    assert manifest['license'] == 'GPL-3.0-only'
    assert manifest['homepage'] == 'https://github.com/MrMybal/CyTools_PersonaRP'
    entries = {entry['kind']: entry for entry in json.loads(_licence(APP / 'licenses.json'))}
    assert entries['Tool']['license'] == 'GPL-3.0-only'
    assert entries['SDK']['license'] == 'GPL-3.0-only'


def test_the_copies_carried_elsewhere_have_the_licence():
    """The ComfyUI nodes and the Colab project leave this folder: they take the licence along."""
    assert _licence(APP / 'comfyui' / 'cytools_personarp' / 'LICENSE') == _licence(ROOT / 'LICENSE')
    import build_colab
    assert "ROOT / 'LICENSE'" in (APP / 'build_colab.py').read_text(encoding='utf-8')
