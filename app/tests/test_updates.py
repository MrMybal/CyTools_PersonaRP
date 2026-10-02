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


# --------------------------------------------- an application built for another runtime

class _Context:
    def __init__(self):
        from cytools_core.runtime import CancellationToken
        self.cancellation = CancellationToken()

    def progress(self, *args, **kwargs):
        pass


def _staging(tmp_path, monkeypatch, installed_abi):
    """An installation whose runtime has `installed_abi`, offered this application's archive."""
    import hashlib
    import zipfile
    built = tmp_path / 'cytools-app.zip'
    with zipfile.ZipFile(built, 'w') as archive:
        for name in ('CyTool.json', 'release.json', 'desktop.py', 'tool.py'):
            archive.write(APP / name, 'app/' + name)
    installed = tmp_path / 'installed' / 'app'
    installed.mkdir(parents=True)
    (installed / 'release.json').write_text(json.dumps({'runtime_abi': installed_abi}),
                                            encoding='utf-8')

    class LocalRelease:
        def __init__(self, root, **options):
            self.root = Path(root)

        def download(self, name, url, **options):
            target = self.root / name
            target.write_bytes(built.read_bytes())
            return {'path': str(target)}

    monkeypatch.setattr(maintenance, 'DownloadManager', LocalRelease)
    monkeypatch.setattr(maintenance, 'APP', installed)
    monkeypatch.setattr(maintenance, 'ROOT', tmp_path)
    monkeypatch.setattr(maintenance, 'RUNTIME', tmp_path / 'runtime')
    monkeypatch.setattr(maintenance, 'SETTINGS', tmp_path / 'settings')
    digest = hashlib.sha256(built.read_bytes()).hexdigest()
    url = 'https://github.com/MrMybal/CyTools_PersonaRP/releases/download/v%s/cytools-app.zip'
    return {'kind': 'app', 'repository': 'MrMybal/CyTools_PersonaRP', 'version': 'v' + INSTALLED,
            'assets': [{'name': 'cytools-app.zip', 'browser_download_url': url % INSTALLED,
                        'digest': 'sha256:' + digest, 'size': built.stat().st_size}]}


def test_an_application_for_the_sdk_010_runtime_is_refused_by_an_older_installation(
        tmp_path, monkeypatch):
    """0.1.2 declares SDK 0.10 exclusion groups an SDK 0.9 runtime would silently ignore."""
    release = json.loads((APP / 'release.json').read_text(encoding='utf-8'))
    assert 'cytools010' in release['runtime_abi'] and release['runtime_abi'] == maintenance.RUNTIME_ABI
    state = _staging(tmp_path, monkeypatch, 'python311-cytools09-imgui192-personarp01')
    with pytest.raises(CyToolError) as refused:
        maintenance.stage_update(_Context(), state)
    assert refused.value.code == 'IncompatibleRuntime'
    assert not (tmp_path / 'settings' / 'app-pending.json').exists()


def test_the_same_runtime_stages_the_application(tmp_path, monkeypatch):
    state = _staging(tmp_path, monkeypatch, maintenance.RUNTIME_ABI)
    staged = maintenance.stage_update(_Context(), state)
    pending = json.loads((tmp_path / 'settings' / 'app-pending.json').read_text(encoding='utf-8'))
    assert staged['version'] == 'v' + INSTALLED and pending['version'] == INSTALLED
    assert set(pending['files']) == {'CyTool.json', 'release.json', 'desktop.py', 'tool.py'}
