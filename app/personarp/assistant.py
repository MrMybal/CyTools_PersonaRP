"""Free discussion threads: talking to a model without playing anybody.

This is the place to think out loud before a character exists — argue about a world, test
an idea, ask a question. It is deliberately separate from a scene: no sheet, no persona, no
scene directive, no voice. Several threads can be open at once, each its own conversation,
because working on two characters at the same time is the normal case.

A thread is a document in data/assistant/<id>.json, written after every turn. Nothing has
to be saved by hand; the draft is kept too, so closing the window mid-sentence loses
nothing. Removing a thread moves it to data/assistant/.trash.
"""
import time
import uuid

from cytools_core import CyToolError

from .library import _safe, now, slug
from .paths import DATA, read_json, write_json

FORMAT = 'cytools-personarp-assistant'
SCHEMA_VERSION = 1
THREADS = DATA / 'assistant'
MAX_TURNS = 500

DEFAULT_SYSTEM = (
    "Tu es un assistant d'ecriture. Tu aides a inventer et a mettre au point des personnages, "
    "des mondes et des scenes. Tu discutes normalement : tu poses des questions, tu proposes, "
    "tu contredis quand c'est utile. Tu ne joues aucun personnage et tu ne pretends jamais "
    "avoir enregistre quoi que ce soit.")


def path_for(identifier):
    return THREADS / (_safe(identifier) + '.json')


def exists(identifier):
    return path_for(identifier).is_file()


def create(title='', system=''):
    identifier = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4]
    document = {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'id': identifier,
                'title': title or 'Discussion', 'system': system or DEFAULT_SYSTEM,
                'created': now(), 'modified': now(), 'turns': [], 'draft': '',
                'llm_model': '', 'device': '', 'temperature': 0.7, 'response_length': 800}
    write_json(path_for(identifier), document)
    return document


def get(identifier):
    document = read_json(path_for(identifier))
    if not document:
        raise CyToolError('NotFound', 'Unknown discussion: ' + str(identifier))
    return document


def save(document):
    if not document.get('id'):
        raise CyToolError('InvalidParameters', 'A discussion needs an identifier.')
    document['format'] = FORMAT
    document['schemaVersion'] = SCHEMA_VERSION
    document['modified'] = now()
    document['turns'] = list(document.get('turns') or [])[-MAX_TURNS:]
    write_json(path_for(document['id']), document)
    return document


def listing():
    items = []
    if not THREADS.is_dir():
        return items
    for item in sorted(THREADS.glob('*.json'), reverse=True):
        document = read_json(item)
        if document:
            items.append({'id': document.get('id', item.stem),
                          'title': document.get('title', ''),
                          'turns': len(document.get('turns') or []),
                          'modified': document.get('modified', ''),
                          'llm_model': document.get('llm_model', '')})
    return items


def append(document, role, content):
    document.setdefault('turns', []).append({'role': role, 'content': content, 'at': now()})
    return document


def history(document):
    return [{'role': turn.get('role', 'user'), 'content': str(turn.get('content', ''))}
            for turn in document.get('turns', []) if str(turn.get('content', '')).strip()]


def remove(identifier):
    source = path_for(identifier)
    if not source.is_file():
        raise CyToolError('NotFound', 'Unknown discussion: ' + str(identifier))
    trash = THREADS / '.trash'
    trash.mkdir(parents=True, exist_ok=True)
    target = trash / (slug(identifier, 'discussion') + '-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
    source.replace(target)
    return {'id': identifier, 'trash': str(target)}


def suggest_title(text):
    """A thread names itself from its first message, so the tabs are readable."""
    words = ' '.join(str(text or '').split())[:60].strip()
    if not words:
        return 'Discussion'
    return words if len(words) < 60 else words.rsplit(' ', 1)[0] + '…'


def as_context(document, limit=6000):
    """The discussion as material for a proposal, most recent first, within a budget."""
    lines = []
    used = 0
    for turn in reversed(document.get('turns') or []):
        content = ' '.join(str(turn.get('content', '')).split())
        if not content:
            continue
        line = ('Vous: ' if turn.get('role') == 'user' else 'Assistant: ') + content
        if used + len(line) > limit:
            break
        lines.append(line)
        used += len(line)
    lines.reverse()
    return '\n'.join(lines)
