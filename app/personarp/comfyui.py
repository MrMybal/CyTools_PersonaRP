"""Installing the PersonaRP nodes into a ComfyUI.

The nodes (app/comfyui/cytools_personarp) are copied into the custom_nodes folder of the
ComfyUI the person chooses, with a config.json that tells them where this Tool is. They talk
to the Tool over its local API and never import it, so ComfyUI keeps its own Python and the
Tool keeps its own. Installing again replaces the copy; nothing else in ComfyUI is touched.

A ComfyUI can be given as its folder (the one holding custom_nodes), as a base directory, or
as the custom_nodes folder itself. Comfy Desktop installations are found on their own from
the Desktop app's installations.json.
"""
import hashlib
import json
import os
import shutil
from pathlib import Path

from cytools_core import CyToolError

from .paths import APP, ROOT

PACK = APP / 'comfyui' / 'cytools_personarp'
NAME = 'cytools_personarp'
DEFAULT_PORT = 8791


def pack_files():
    return sorted(path for path in PACK.rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts
                  and path.name != 'config.json')


def pack_digest(files=None, root=PACK):
    """One digest for the code of the nodes, to tell an installed copy from a stale one."""
    digest = hashlib.sha256()
    for path in files if files is not None else pack_files():
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _installed_digest(target):
    """The digest of the copy really on disk — not the one its config.json claims."""
    files = [target / source.relative_to(PACK) for source in pack_files()]
    if not all(path.is_file() for path in files):
        return ''
    return pack_digest(files, root=target)


def custom_nodes(path):
    """The custom_nodes folder of a ComfyUI given in any of the usual ways."""
    path = Path(str(path or '').strip().strip('"'))
    if not str(path) or not path.is_absolute():
        raise CyToolError('InvalidParameters', 'Give the full path of the ComfyUI folder.')
    for candidate in (path if path.name == 'custom_nodes' else None, path / 'custom_nodes',
                      path / 'ComfyUI' / 'custom_nodes'):
        if candidate is not None and candidate.is_dir():
            return candidate
    raise CyToolError('NotFound', 'Not a ComfyUI folder (no custom_nodes inside): %s' % path)


def _desktop_configs():
    homes = []
    if os.environ.get('APPDATA'):
        homes.append(Path(os.environ['APPDATA']))
    homes += [Path.home() / '.config', Path.home() / 'Library' / 'Application Support']
    return [home / 'Comfy Desktop' / 'installations.json' for home in homes]


def candidates():
    """ComfyUI folders found without being told: the Comfy Desktop installations."""
    found = []
    for config in _desktop_configs():
        try:
            installations = json.loads(config.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        for installation in installations if isinstance(installations, list) else []:
            if not isinstance(installation, dict):
                continue
            for key in ('adoptedBaseDir', 'baseDir', 'basePath', 'installPath'):
                value = installation.get(key)
                if not value:
                    continue
                try:
                    folder = custom_nodes(value).parent
                except CyToolError:
                    continue
                entry = {'path': str(folder), 'name': installation.get('name') or 'ComfyUI',
                         'source': 'Comfy Desktop',
                         'python': installation.get('adoptedPythonPath', '')}
                if all(entry['path'] != other['path'] for other in found):
                    found.append(entry)
                break
    return found


def status(path):
    try:
        target = custom_nodes(path) / NAME
    except CyToolError as exc:
        return {'path': str(path), 'valid': False, 'installed': False, 'upToDate': False,
                'reason': str(exc)}
    installed = (target / '__init__.py').is_file()
    config = {}
    if installed:
        try:
            config = json.loads((target / 'config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            config = {}
    return {'path': str(path), 'valid': True, 'folder': str(target), 'installed': installed,
            'upToDate': installed and _installed_digest(target) == pack_digest()
            and config.get('tool_root') == str(ROOT),
            'toolRoot': config.get('tool_root', ''), 'port': config.get('port', DEFAULT_PORT),
            'reason': ''}


def install(path, port=DEFAULT_PORT, auto_start=True):
    """Copy the nodes into this ComfyUI and tell them where the Tool is."""
    folder = custom_nodes(path)
    target = folder / NAME
    files = pack_files()
    if not files:
        raise CyToolError('MissingDependency', 'The ComfyUI nodes are missing from ' + str(PACK))
    staging = folder / ('.%s-installing' % NAME)
    if staging.exists():
        shutil.rmtree(staging)
    for source in files:
        destination = staging / source.relative_to(PACK)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    digest = pack_digest()
    (staging / 'config.json').write_text(json.dumps({
        'tool_root': str(ROOT), 'port': int(port), 'auto_start': bool(auto_start),
        'packDigest': digest}, indent=2) + '\n', encoding='utf-8')
    # Only our own folder is replaced, and only once the new copy is complete.
    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)
    return {'folder': str(target), 'files': len(files) + 1, 'packDigest': digest,
            'toolRoot': str(ROOT), 'port': int(port), 'nodes': node_names()}


def node_names():
    """The node identifiers the pack declares, read from its source (it is not imported)."""
    text = (PACK / 'nodes.py').read_text(encoding='utf-8')
    start = text.index('NODE_DISPLAY_NAME_MAPPINGS = {')
    names = []
    for line in text[start:].splitlines()[1:]:
        line = line.strip()
        if line.startswith('}'):
            break
        if ':' in line:
            key, value = line.split(':', 1)
            names.append({'id': key.strip().strip("'\""), 'name': value.strip().rstrip(',').strip("'\"")})
    return names
