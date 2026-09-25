"""Reference photographs attached to a character sheet.

A sheet can carry pictures: a portrait, a full-body shot, an outfit, a detail. They are
copied next to the character in data/personas/<id>.images so the sheet stays self-contained
and can be exported whole, and each one records its size and digest so a replaced file is
noticed.

They are reference material for *you* and input for the vision model that fills the
appearance branch. They are never sent to the roleplay model, which reads text only.
"""
import hashlib
import io
import shutil
import time
from pathlib import Path

from cytools_core import CyToolError

from .library import now, slug
from .paths import PERSONAS, read_json

ACCEPTED = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp', '.bmp': 'image/bmp'}
MAX_BYTES = 40 * 1024 ** 2
MAX_PER_PERSONA = 32

# What a vision model actually needs. A modern phone photo is far larger than this and only
# costs encoding time and socket traffic; the long edge here keeps faces legible.
SEND_LONG_EDGE = 1024
SEND_QUALITY = 88


def folder(persona_id):
    from .library import _safe
    return PERSONAS / (_safe(persona_id) + '.images')


def _digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def probe(path):
    """Format and pixel size, refusing anything that is not an image we can send."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in ACCEPTED:
        raise CyToolError('InvalidInput',
                          'Unsupported image type "%s". Use PNG, JPEG, WebP or BMP.' % suffix)
    if not path.is_file():
        raise CyToolError('MissingInput', 'Image not found: ' + str(path))
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise CyToolError('InvalidInput',
                          'Image is %.1f MB; keep reference photographs under %d MB.'
                          % (size / 1e6, MAX_BYTES // 1024 ** 2))
    try:
        from PIL import Image
        with Image.open(path) as image:
            width, height = image.size
            kind = image.format
    except CyToolError:
        raise
    except Exception as exc:                                   # noqa: BLE001 - reported as ours
        raise CyToolError('InvalidInput', 'Unreadable image: %s' % exc) from exc
    return {'width': int(width), 'height': int(height), 'bytes': int(size),
            'format': kind or suffix.lstrip('.').upper(), 'mimeType': ACCEPTED[suffix]}


def add(persona, source, role='reference', caption=''):
    """Copy a photograph beside the sheet and return the updated reference list."""
    source = Path(source)
    details = probe(source)
    references = list(persona.get('references') or [])
    if len(references) >= MAX_PER_PERSONA:
        raise CyToolError('InvalidParameters',
                          'A sheet holds at most %d photographs.' % MAX_PER_PERSONA)
    target_folder = folder(persona['id'])
    target_folder.mkdir(parents=True, exist_ok=True)
    stem = slug(Path(source).stem, 'image')
    target = target_folder / (stem + source.suffix.lower())
    index = 2
    while target.exists():
        target = target_folder / ('%s-%d%s' % (stem, index, source.suffix.lower()))
        index += 1
    shutil.copyfile(source, target)
    references.append({'file': str(target), 'role': role, 'caption': caption,
                       'sha256': _digest(target), 'width': details['width'],
                       'height': details['height'], 'bytes': details['bytes'],
                       'mimeType': details['mimeType'], 'added': now()})
    persona['references'] = references
    return persona


def remove(persona, file_path):
    """Move a photograph to the character's image trash. Nothing is deleted."""
    references = list(persona.get('references') or [])
    kept = [item for item in references if item.get('file') != str(file_path)]
    if len(kept) == len(references):
        raise CyToolError('NotFound', 'This sheet does not carry: ' + str(file_path))
    source = Path(file_path)
    trash = folder(persona['id']) / '.trash'
    moved = ''
    if source.is_file() and source.parent.resolve() == folder(persona['id']).resolve():
        trash.mkdir(parents=True, exist_ok=True)
        destination = trash / (source.stem + '-' + time.strftime('%Y%m%d-%H%M%S') + source.suffix)
        source.replace(destination)
        moved = str(destination)
    persona['references'] = kept
    return persona, moved


def verify(persona):
    """Which photographs are still present and unchanged."""
    report = []
    for item in persona.get('references') or []:
        path = Path(item.get('file', ''))
        if not path.is_file():
            report.append({'file': item.get('file', ''), 'ok': False, 'reason': 'missing'})
        elif item.get('sha256') and _digest(path) != item['sha256']:
            report.append({'file': str(path), 'ok': False, 'reason': 'changed since it was added'})
        else:
            report.append({'file': str(path), 'ok': True, 'reason': ''})
    return report


def encoded(path, long_edge=SEND_LONG_EDGE):
    """A data URL for the vision model, downscaled so a 12 MP photo is not sent whole."""
    import base64
    from PIL import Image
    path = Path(path)
    if not path.is_file():
        raise CyToolError('MissingInput', 'Image not found: ' + str(path))
    with Image.open(path) as image:
        image = image.convert('RGB')
        if max(image.size) > long_edge:
            scale = long_edge / max(image.size)
            image = image.resize((max(1, round(image.width * scale)),
                                  max(1, round(image.height * scale))), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=SEND_QUALITY)
        payload = buffer.getvalue()
        sent = image.size
    return {'url': 'data:image/jpeg;base64,' + base64.b64encode(payload).decode('ascii'),
            'sentWidth': sent[0], 'sentHeight': sent[1], 'sentBytes': len(payload)}


def library_listing(persona_id=''):
    """Every photograph held by the library, newest sheet first.

    Reading the sheets is cheap — they are small documents — and it keeps the gallery
    honest: a picture that has left the disk is listed as missing rather than skipped.
    """
    from .library import personas
    items = []
    for entry in personas.list():
        if persona_id and entry['id'] != persona_id:
            continue
        try:
            sheet = personas.get(entry['id'])
        except Exception:                                  # noqa: BLE001 - a broken sheet is not fatal
            continue
        for reference in sheet.get('references') or []:
            path = Path(reference.get('file', ''))
            items.append({**reference, 'persona_id': sheet['id'],
                          'persona_name': sheet.get('name', sheet['id']),
                          'present': path.is_file()})
    return items


def bundled(persona):
    """Existing photographs of a sheet, for an export archive."""
    items = []
    for item in persona.get('references') or []:
        path = Path(item.get('file', ''))
        if path.is_file():
            items.append((item, path))
    return items
