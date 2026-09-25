"""Conversations, stored per character so a scene can be picked up days later.

A turn keeps more than its text: the scene directive the model produced, the delivery
annotations it wrote, and the audio take if one was rendered. The directive is kept in the
saved conversation but deliberately left out of the prompt on the next turn — see
prompting.history_for_model.
"""
import time
import uuid

from cytools_core import CyToolError

from .library import _safe, now, slug
from .paths import SESSIONS, read_json, write_json

FORMAT = 'cytools-personarp-session'
SCHEMA_VERSION = 1


def folder(persona_id):
    return SESSIONS / _safe(persona_id)


def path(persona_id, session_id):
    return folder(persona_id) / (_safe(session_id) + '.json')


def create(persona_id, title=''):
    identifier = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4]
    document = {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'id': identifier,
                'persona_id': _safe(persona_id), 'title': title or ('Scene ' + now()),
                'created': now(), 'modified': now(), 'turns': [], 'draft': '',
                'world_id': '', 'participants': []}
    write_json(path(persona_id, identifier), document)
    return document


def get(persona_id, session_id):
    document = read_json(path(persona_id, session_id))
    if not document:
        raise CyToolError('NotFound', 'Unknown session: ' + str(session_id))
    return document


def save(document):
    if not document.get('persona_id') or not document.get('id'):
        raise CyToolError('InvalidParameters', 'A session needs a persona and an identifier.')
    document['format'] = FORMAT
    document['schemaVersion'] = SCHEMA_VERSION
    document['modified'] = now()
    write_json(path(document['persona_id'], document['id']), document)
    return document


def listing(persona_id=''):
    items = []
    roots = [folder(persona_id)] if persona_id else \
        ([p for p in SESSIONS.iterdir() if p.is_dir()] if SESSIONS.is_dir() else [])
    for root in roots:
        if not root.is_dir():
            continue
        for item in sorted(root.glob('*.json'), reverse=True):
            document = read_json(item)
            if document:
                items.append({'id': document.get('id', item.stem),
                              'persona_id': document.get('persona_id', root.name),
                              'title': document.get('title', ''),
                              'turns': len(document.get('turns', [])),
                              'modified': document.get('modified', '')})
    return items


def append_turn(document, role, content, **extra):
    turn = {'role': role, 'content': content, 'at': now()}
    turn.update({k: v for k, v in extra.items() if v not in (None, '', [], {})})
    document.setdefault('turns', []).append(turn)
    return turn


def history(document):
    """The plain role/content view the prompt builder consumes."""
    return [{'role': turn.get('role', 'user'), 'content': str(turn.get('content', ''))}
            for turn in document.get('turns', []) if str(turn.get('content', '')).strip()]


def remove(persona_id, session_id):
    source = path(persona_id, session_id)
    if not source.is_file():
        raise CyToolError('NotFound', 'Unknown session: ' + str(session_id))
    trash = folder(persona_id) / '.trash'
    trash.mkdir(parents=True, exist_ok=True)
    target = trash / (slug(session_id, 'session') + '-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
    source.replace(target)
    return {'id': session_id, 'trash': str(target)}
