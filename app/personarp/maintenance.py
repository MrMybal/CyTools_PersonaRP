"""GitHub updates for three independent streams: the application, the engine, the weights.

Weights are not handled here — they have their own catalogue, licences and revisions in
models.py. An update is staged under runtime/updates, verified there (provenance, Tool
identity, version, runtime ABI, archive containment, and a compile pass that never imports
the candidate code), and only then activated. data/ is never part of a replacement, the
previous version is kept, and a rollback is always available.
"""
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from cytools_core import CyToolError, load_manifest
from cytools_core.downloads import DownloadManager

from .locks import exclusive
from .models import sha
from .paths import APP, DATA, ROOT, RUNTIME, SETTINGS, TOOL_ID, read_json, write_json

ENGINE_REPO = 'ggml-org/llama.cpp'
RUNTIME_ABI = 'python311-cytools09-imgui192-personarp01'
MAX_ARCHIVE_BYTES = 1024 ** 3
MAX_ASSET_BYTES = 512 * 1024 ** 2


def default_repository():
    """Where this application's updates come from: release.json, which ships with it."""
    return str(read_json(APP / 'release.json').get('repository') or '').strip()


def repository(value):
    value = str(value or '').strip() or default_repository()
    value = value.removeprefix('https://github.com/').removesuffix('.git').rstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', value) or value.split('/')[-1] in ('.', '..'):
        raise CyToolError('InvalidParameters', 'Expected a GitHub repository as owner/name.')
    return value


def github(path):
    request = urllib.request.Request(
        'https://api.github.com/' + path,
        headers={'User-Agent': 'CyTools-PersonaRP', 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            import json
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # Updates are read from GitHub without credentials: a private repository, or one
            # with no published release yet, answers 404 all the same.
            raise CyToolError(
                'MissingRelease',
                'No update can be read from GitHub — the repository is private, or no release '
                'has been published yet; updates are read without credentials, so the '
                'repository has to be public with a published release: '
                + path.split('/releases')[0].removeprefix('repos/')) from exc
        raise CyToolError('NetworkError', 'GitHub answered HTTP %d.' % exc.code) from exc
    except urllib.error.URLError as exc:
        raise CyToolError('NetworkError', 'GitHub cannot be reached: %s' % exc.reason) from exc


def safe_extract(archive, destination):
    """Extract refusing path traversal, absolute names, duplicates, links and oversized sets."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    def check(name):
        path = PurePosixPath(name)
        if '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts \
                or any(part.endswith(('.', ' ')) for part in path.parts):
            raise CyToolError('InvalidArchive', 'Forbidden path in archive: ' + name)
        if not (destination / name).resolve().is_relative_to(destination):
            raise CyToolError('InvalidArchive', 'Archive entry escapes the destination: ' + name)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            if sum(x.file_size for x in bundle.infolist()) > MAX_ARCHIVE_BYTES:
                raise CyToolError('InvalidArchive', 'Archive is too large.')
            seen = set()
            for item in bundle.infolist():
                check(item.orig_filename)
                check(item.filename)
                if item.filename.casefold() in seen:
                    raise CyToolError('InvalidArchive', 'Duplicate entry in archive.')
                seen.add(item.filename.casefold())
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise CyToolError('InvalidArchive', 'Links are not allowed in archives.')
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            if sum(x.size for x in members) > MAX_ARCHIVE_BYTES:
                raise CyToolError('InvalidArchive', 'Archive is too large.')
            for item in members:
                check(item.name)
                if not (item.isfile() or item.isdir()):
                    raise CyToolError('InvalidArchive', 'Links and devices are not allowed.')
            for item in members:
                target = destination / item.name
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(item) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(item.mode & 0o777)


def check_update(kind, repo=''):
    if kind == 'engine':
        repo = ENGINE_REPO
        releases = github('repos/' + repo + '/releases?per_page=20')
        suffix = 'bin-win-cpu-x64.zip' if os.name == 'nt' else 'bin-ubuntu-x64.tar.gz'
        release = next((r for r in releases
                        if not r['draft'] and re.fullmatch(r'b[0-9]+', r['tag_name'])
                        and any(a['name'].endswith(suffix) for a in r['assets'])), None)
        if release is None:
            raise CyToolError('MissingRelease', 'No compatible CPU engine release found.')
        assets = [a for a in release['assets'] if a['name'].endswith(suffix)]
        installed = read_json(SETTINGS / 'engine.json').get('version', '')
    else:
        repo = repository(repo)
        release = github('repos/' + repo + '/releases/latest')
        assets = release['assets']
        installed = read_json(APP / 'release.json').get('version', '0.1.0')
    return {'kind': kind, 'repository': repo, 'version': release['tag_name'],
            'installed': installed, 'updateAvailable': newer(release['tag_name'], installed),
            'assets': assets}


def _numbers(version):
    found = re.findall(r'\d+', str(version))
    return tuple(int(number) for number in found) if found else None


def newer(published, installed):
    """Whether the published release is more recent than what is installed.

    Tags are usually written v0.2.0 and versions 0.2.0, engine builds b11057: compared as
    numbers, so 0.1.10 follows 0.1.9 and an older release is never offered as an update.
    Without numbers on either side, any difference counts (nothing installed, for instance).
    """
    mine, theirs = _numbers(installed), _numbers(published)
    if mine is None or theirs is None:
        return str(published).lstrip('v') != str(installed).lstrip('v')
    return theirs > mine


def stage_update(context, state):
    kind = state['kind']
    repo = repository(state['repository'])
    if kind == 'engine' and repo != ENGINE_REPO:
        raise CyToolError('InvalidParameters', 'Unexpected engine source.')
    assets = state['assets']
    asset = assets[0] if kind == 'engine' else next((a for a in assets if a['name'] == 'cytools-app.zip'), None)
    if not asset:
        raise CyToolError('MissingRelease', 'cytools-app.zip is missing from the release.')
    url = asset['browser_download_url']
    if not url.startswith('https://github.com/' + repo + '/releases/download/'):
        raise CyToolError('InvalidParameters', 'Asset does not come from the configured repository.')
    digest = (asset.get('digest') or '').removeprefix('sha256:')
    if not re.fullmatch('[a-f0-9]{64}', digest):
        raise CyToolError('MissingChecksum',
                          'GitHub did not publish a SHA-256 for this asset. A published checksum '
                          'is not an independent signature, but without one nothing can be verified.')
    if asset['size'] > MAX_ASSET_BYTES:
        raise CyToolError('InvalidParameters', 'Release asset is too large.')
    stage = RUNTIME / 'updates' / kind / digest
    stage.mkdir(parents=True, exist_ok=True)
    name = 'release.zip' if kind == 'app' or os.name == 'nt' else 'release.tar.gz'
    result = DownloadManager(stage).download(
        name, url, sha256=digest, size=asset['size'], cancellation=context.cancellation,
        progress=lambda done, total: context.progress(min(90, 90 * done / max(total, 1)),
                                                      currentStep='Downloading the update'))
    context.cancellation.check()
    candidate = stage / ('unpacked-' + str(time.time_ns()))
    safe_extract(result['path'], candidate)
    if kind == 'engine':
        executable_name = 'llama-completion.exe' if os.name == 'nt' else 'llama-completion'
        found = list(candidate.rglob(executable_name))
        if len(found) != 1:
            raise CyToolError('InvalidArchive', 'Engine executable missing or ambiguous.')
        executable = found[0]
        tested = subprocess.run([str(executable), '--version'], capture_output=True, timeout=30,
                                creationflags=0x08000000 if os.name == 'nt' else 0)
        if tested.returncode:
            raise CyToolError('IncompatibleEngine', 'This engine build does not run on this machine.')
        pending = {'path': str(executable.relative_to(ROOT)), 'version': state['version'],
                   'sha256': sha(executable)}
    else:
        app = candidate / 'app'
        manifest = load_manifest(app / 'CyTool.json')
        release = read_json(app / 'release.json')
        if manifest['id'] != TOOL_ID or manifest['version'] != state['version'].lstrip('v'):
            raise CyToolError('InvalidUpdate', 'Tool identity or version does not match the release.')
        if release.get('runtime_abi') != read_json(APP / 'release.json').get('runtime_abi', RUNTIME_ABI) \
                or release.get('platform') not in ('any', sys.platform):
            raise CyToolError('IncompatibleRuntime',
                              'Runtime or platform mismatch: a full installation is required.')
        if not (app / 'desktop.py').is_file():
            raise CyToolError('InvalidUpdate', 'The candidate has no interface.')
        # Compile without importing candidate code or touching installed dependencies.
        for source in app.rglob('*.py'):
            compile(source.read_text('utf-8'), str(source), 'exec')
        pending = {'path': str(app.relative_to(ROOT)), 'version': manifest['version'],
                   'files': {str(f.relative_to(app)): sha(f) for f in app.rglob('*') if f.is_file()}}
    context.cancellation.check()
    write_json(SETTINGS / (kind + '-pending.json'), pending)
    context.progress(100, currentStep='Update staged and verified')
    return {'message': 'Update staged. Activate the engine, or restart to activate the application.',
            'version': state['version']}


def activate_engine():
    pending = read_json(SETTINGS / 'engine-pending.json')
    if not pending:
        raise CyToolError('NotFound', 'No engine has been staged.')
    path = (ROOT / pending['path']).resolve()
    if not path.is_relative_to((RUNTIME / 'updates/engine').resolve()) or sha(path) != pending['sha256']:
        raise CyToolError('IntegrityFailure', 'The staged engine changed after verification.')
    previous = read_json(SETTINGS / 'engine.json')
    if previous:
        write_json(SETTINGS / 'engine-previous.json', previous)
    write_json(SETTINGS / 'engine.json', pending)
    (SETTINGS / 'engine-pending.json').unlink()


def rollback_engine():
    previous = read_json(SETTINGS / 'engine-previous.json')
    if not previous:
        raise CyToolError('NotFound', 'No previous engine to restore.')
    path = (ROOT / previous['path']).resolve()
    if not path.is_relative_to(RUNTIME.resolve()) or sha(path) != previous['sha256']:
        raise CyToolError('IntegrityFailure', 'The previous engine is no longer valid.')
    current = read_json(SETTINGS / 'engine.json')
    write_json(SETTINGS / 'engine.json', previous)
    write_json(SETTINGS / 'engine-previous.json', current)


def apply_pending_app():
    """Swap the application directory at launch, under the lock, keeping the old one."""
    pending = read_json(SETTINGS / 'app-pending.json')
    if not pending:
        return
    import psutil
    for process in psutil.process_iter(['pid', 'cmdline']):
        if process.pid == os.getpid():
            continue
        try:
            if any(str(APP).casefold() in str(arg).casefold() for arg in (process.info['cmdline'] or [])):
                raise CyToolError('Busy', 'Close the other windows and services of this Tool first.')
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    with exclusive():
        source = (ROOT / pending['path']).resolve()
        if not source.is_relative_to((RUNTIME / 'updates/app').resolve()):
            raise CyToolError('InvalidUpdate', 'Invalid application source.')
        actual = {str(f.relative_to(source)): sha(f) for f in source.rglob('*')
                  if f.is_file() and '__pycache__' not in f.parts}
        if actual != pending['files']:
            raise CyToolError('IntegrityFailure', 'The staged application changed after verification.')
        backup = RUNTIME / 'updates/app' / ('previous-' + str(time.time_ns()))
        previous = {'path': str(backup.relative_to(ROOT)),
                    'version': read_json(APP / 'release.json').get('version'),
                    'files': {str(f.relative_to(APP)): sha(f) for f in APP.rglob('*')
                              if f.is_file() and '__pycache__' not in f.parts}}
        APP.rename(backup)
        try:
            source.rename(APP)
        except BaseException:
            backup.rename(APP)
            raise
        write_json(SETTINGS / 'app-previous.json', previous)
        (SETTINGS / 'app-pending.json').unlink()


def update(context, parameters):
    with exclusive(context):
        kind, action = parameters['kind'], parameters['action']
        if action == 'rollback':
            if kind == 'engine':
                rollback_engine()
            else:
                previous = read_json(SETTINGS / 'app-previous.json')
                if not previous:
                    raise CyToolError('NotFound', 'No previous application to restore.')
                write_json(SETTINGS / 'app-pending.json', previous)
            return {'message': 'Rollback prepared (the application restores on restart).'}
        if action == 'activate':
            if kind != 'engine':
                return {'message': 'Close and relaunch the Tool to activate the application.'}
            activate_engine()
            return {'message': 'Engine activated.'}
        state = check_update(kind, parameters.get('repository', ''))
        if action == 'download':
            return stage_update(context, state)
        return {'message': 'Latest published version: ' + state['version'],
                'version': state['version'], 'updateAvailable': state['updateAvailable']}
