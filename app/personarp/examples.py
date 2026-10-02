"""The example worlds shipped with the Tool, ready to import.

Each file in app/examples is an ordinary export bundle: a world and its cast. They live with
the application, not in data/, because they are not yours until you import them — and an
import is a copy, so playing with an example never changes the example.
"""
from cytools_core import CyToolError

from . import library
from .paths import APP

EXAMPLES = APP / 'examples'


def bundles():
    """The example files: a .zip carries its voices' recordings, a .json has none."""
    if not EXAMPLES.is_dir():
        return []
    return sorted(list(EXAMPLES.glob('*.json')) + list(EXAMPLES.glob('*.zip')),
                  key=lambda path: path.name)


def listing():
    items = []
    if not EXAMPLES.is_dir():
        return items
    for path in bundles():
        try:
            bundle = library._read_bundle(path)[0]
        except (OSError, ValueError, CyToolError):
            continue
        world = (bundle.get('worlds') or [{}])[0]
        items.append({
            'id': path.stem, 'file': str(path),
            'world': world.get('name', path.stem), 'worldId': world.get('id', ''),
            'genre': world.get('genre', ''), 'tone': world.get('tone', ''),
            'summary': world.get('summary', ''),
            'imported': bool(world.get('id')) and library.worlds.exists(world['id']),
            'voices': len(bundle.get('voices') or []),
            'scenes': [{'title': scene.get('title', ''), 'lines': len(scene.get('turns') or [])}
                       for scene in bundle.get('sessions') or []],
            'characters': [{'id': sheet.get('id', ''), 'name': sheet.get('name', ''),
                            'summary': sheet.get('summary', '')}
                           for sheet in bundle.get('personas', [])],
        })
    return items
