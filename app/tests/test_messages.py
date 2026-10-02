"""The messages operations send back are shown in French in a French window.

The catalogue is read from the code itself: a message added without its translation fails
here, as a window string without its entry fails test_locale.
"""
import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from personarp import messages                                              # noqa: E402

CATALOG = json.loads((APP / 'locales' / 'messages.json').read_text(encoding='utf-8'))


def test_every_message_of_the_code_has_its_french():
    missing = {key: where for key, where in messages.templates().items()
               if not (CATALOG.get(key) or {}).get('fr')}
    assert missing == {}


def test_a_translation_keeps_every_variable_part():
    for key, entry in CATALOG.items():
        assert sorted(set(re.findall(r'\{\d+\}', key))) == \
            sorted(set(re.findall(r'\{\d+\}', entry['fr']))), key


def test_the_code_is_read_for_every_kind_of_message():
    found = messages.templates()
    assert 'Unknown session: {0}' in found                          # 'text: ' + value
    assert 'This line has no {0} translation yet; translate the scene first.' in found   # %
    assert "{0} The character's own voice was used instead." in found   # a reason, then more
    assert '{0} The character falls back to a preset speaker.' in found  # reason += '...'
    assert 'No character called "{0}".' in found                    # returned, not raised
    assert 'Id already used by another line: {0} (line {1})' in found


def test_messages_are_translated_whole_with_their_values():
    assert messages.translate('This line has no German translation yet; translate the scene '
                              'first.', 'fr') == \
        "Cette réplique n'a pas encore de traduction en allemand ; traduisez d'abord la scène."
    # A reason followed by what happens next: both parts are known messages.
    assert messages.translate('The voice "brannoc" is not in the library. The character falls '
                              'back to a preset speaker.', 'fr') == \
        'La voix « brannoc » n\'est pas dans la bibliothèque. Le personnage revient à une voix ' \
        'prédéfinie.'
    assert messages.translate('Unknown session: 2026-09-23-a', 'fr') == 'Scène inconnue : 2026-09-23-a'
    assert messages.translate('A JSON batch is a list of lines, or {"lines": [...]}.', 'fr') == \
        'Un lot JSON est une liste de répliques, ou {"lines": [...]}.'


def test_what_is_unknown_or_english_is_left_alone():
    assert messages.translate('Something nobody wrote.', 'fr') == 'Something nobody wrote.'
    assert messages.translate('Unknown session: x', 'en') == 'Unknown session: x'
    assert messages.translate('', 'fr') == ''


def test_a_job_error_is_described_by_its_message():
    error = {'code': 'Busy', 'message': 'Another generation or maintenance task is using this Tool.'}
    assert messages.describe(error, 'fr') == \
        'Une autre génération ou tâche de maintenance utilise cet outil.'
    assert messages.describe({'code': 'Weird'}, 'fr') == 'Weird'
