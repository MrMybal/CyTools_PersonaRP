"""Where the updates of the application come from, and what is said when GitHub has none.

No network here: GitHub is replaced by a stub.
"""
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from cytools_core import CyToolError                                      # noqa: E402

from personarp import maintenance                                         # noqa: E402

INSTALLED = json.loads((APP / 'release.json').read_text(encoding='utf-8'))['version']


def test_the_application_ships_with_its_repository():
    release = json.loads((APP / 'release.json').read_text(encoding='utf-8'))
    assert release['repository'] == 'MrMybal/CyTools_PersonaRP'
    assert maintenance.repository('') == 'MrMybal/CyTools_PersonaRP'
    assert maintenance.repository('https://github.com/MrMybal/CyTools_PersonaRP.git') \
        == 'MrMybal/CyTools_PersonaRP'
    assert maintenance.repository('someone/else') == 'someone/else'          # still yours to set
    with pytest.raises(CyToolError):
        maintenance.repository('not a repository')


def test_a_check_without_a_repository_asks_the_shipped_one(monkeypatch):
    asked = []

    def fake(path):
        asked.append(path)
        return {'tag_name': '0.2.0', 'assets': []}
    monkeypatch.setattr(maintenance, 'github', fake)
    state = maintenance.check_update('app', '')
    assert asked == ['repos/MrMybal/CyTools_PersonaRP/releases/latest']
    assert state['repository'] == 'MrMybal/CyTools_PersonaRP'
    assert state['updateAvailable'] and state['installed'] == INSTALLED


def test_a_private_or_empty_repository_is_explained(monkeypatch):
    def not_found(request, timeout=30):
        raise urllib.error.HTTPError(request.full_url, 404, 'Not Found', {}, io.BytesIO(b'{}'))
    monkeypatch.setattr(maintenance.urllib.request, 'urlopen', not_found)
    with pytest.raises(CyToolError) as failure:
        maintenance.check_update('app', '')
    assert failure.value.code == 'MissingRelease'
    message = str(failure.value)
    assert 'MrMybal/CyTools_PersonaRP' in message and 'private' in message
    assert 'no release has been published yet' in message
    assert message.endswith(': MrMybal/CyTools_PersonaRP')           # translatable by its prefix


def test_a_tag_written_with_a_v_is_the_installed_version(monkeypatch):
    monkeypatch.setattr(maintenance, 'github', lambda path: {'tag_name': 'v' + INSTALLED, 'assets': []})
    assert maintenance.check_update('app', '')['updateAvailable'] is False
    monkeypatch.setattr(maintenance, 'github', lambda path: {'tag_name': 'v9.0.0', 'assets': []})
    assert maintenance.check_update('app', '')['updateAvailable'] is True


def test_only_a_more_recent_release_is_an_update():
    assert maintenance.newer('v0.1.1', '0.1.0') and maintenance.newer('0.1.10', '0.1.9')
    assert not maintenance.newer('v0.1.0', '0.1.1')             # never offered backwards
    assert not maintenance.newer('v0.1.1', '0.1.1')
    assert maintenance.newer('b11060', 'b11057') and not maintenance.newer('b11057', 'b11057')
    assert maintenance.newer('b11057', '')                       # no engine installed yet
