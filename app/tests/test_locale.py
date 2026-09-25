"""The French interface is complete, and stays complete.

A string added to the window without its French entry shows up in English for a French
user; nothing else would notice. The scan reads the window's code the way the window
translates it (see locale_strings.py), so a new label fails here until it is translated,
and a label built in a way no catalogue entry can match fails too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import locale_strings                                                     # noqa: E402
from gui.voice_panel import IN_LANGUAGE                                  # noqa: E402
from personarp.schemas import LANGUAGES                                   # noqa: E402

# Shown through tr() from data rather than from a literal: the scan cannot see them.
DYNAMIC = (['Auto'] + LANGUAGES + list(IN_LANGUAGE.values())
           + ['designed', 'generated', 'imported'] + locale_strings.JOB_STATES)


def test_every_visible_string_has_french():
    found, _ = locale_strings.scan()
    absent = locale_strings.missing(found)
    assert absent == {}, 'No French for: %s' % sorted(absent.items(), key=lambda item: item[1])


def test_no_label_is_built_where_the_catalogue_cannot_match_it():
    _, flagged = locale_strings.scan()
    assert flagged == []


def test_text_literals_go_through_tr():
    """The facade translates labels, not texts: a text literal without tr() stays in English
    whatever the catalogue holds (the Batches tab titles did, with their French written)."""
    import ast
    untranslated = []
    for path in locale_strings.FILES:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if not isinstance(node, ast.Call):
                continue
            owner, name = locale_strings._callee(node)
            if owner not in ('imgui', 'raw') or name not in locale_strings.FACADE_TEXTS | {'text_colored'}:
                continue
            position = 1 if name == 'text_colored' else 0
            if len(node.args) > position:
                text = locale_strings._constant(node.args[position])
                if text and locale_strings.wordy(text) and text != 'PersonaRP':
                    untranslated.append('%s:%d %r' % (path.name, node.lineno, text))
    assert untranslated == []


def test_values_shown_from_data_have_french():
    absent = locale_strings.missing({text: 'dynamic' for text in DYNAMIC})
    assert absent == {}


def test_french_survives_a_second_translation():
    """Labels are often translated by the code and again by the facade."""
    found, _ = locale_strings.scan()
    assert locale_strings.unstable(list(found) + DYNAMIC) == []


def test_the_scan_really_finds_strings():
    """A scan that finds nothing would pass the tests above for any code."""
    found, _ = locale_strings.scan()
    for expected in ('Translate the scene', 'Say it', 'Stable voice', 'Identity',
                     'Take ready', 'Characters'):
        assert expected in found, expected
    assert len(found) > 400


def test_the_scan_catches_an_untranslated_label(tmp_path):
    panel = tmp_path / 'panel.py'
    panel.write_text("from ui_common import imgui, raw, tr\n"
                     "def draw(app, name):\n"
                     "    imgui.button('Launch the rocket')\n"
                     "    raw().text_wrapped('Shown raw')\n"
                     "    imgui.text('Hello ' + name)\n", encoding='utf-8')
    found, flagged = locale_strings.scan([panel])
    assert 'Launch the rocket' in locale_strings.missing(found)
    reasons = [why for _, why, _ in flagged]
    assert any('without translation' in why for why in reasons)
    assert any('built before translation' in why for why in reasons)
