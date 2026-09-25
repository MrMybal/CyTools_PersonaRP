"""Stable voices: turning one short take into the voice a character keeps for good.

The idea is simple and it is what makes dialogue usable. You produce (or supply) a dozen
seconds of speech once; from then on every line the character speaks is cloned from that
same recording, so the voice does not drift between replies, between scenes or between
sessions. The take, its exact transcript and the model that will read it are stored
together, because a clone needs all three to reproduce itself.

A voice is a document in data/voices/<id>.json with its recording beside it. Removing one
moves it to data/voices/.trash; nothing here deletes a recording.
"""
import hashlib
import shutil
import time
from pathlib import Path

from cytools_core import CyToolError

from ..library import now, slug
from ..paths import VOICES, read_json, write_json
from ..schemas import normalize_stable_voice

# A reference that is too short does not carry a voice; one that is too long mostly wastes
# encoding time. These are the bounds the interface advertises.
IDEAL_SECONDS = (12.0, 24.0)
ACCEPTED_SECONDS = (4.0, 120.0)


def _digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def probe(path):
    """Duration, sample rate and channels of a recording, without loading all of it."""
    import soundfile
    try:
        info = soundfile.info(str(path))
    except Exception as exc:                                  # noqa: BLE001 - reported as a CyToolError
        raise CyToolError('InvalidInput', 'Unreadable recording: %s' % exc) from exc
    return {'seconds': float(info.frames) / info.samplerate if info.samplerate else 0.0,
            'sampleRate': int(info.samplerate), 'channels': int(info.channels),
            'format': info.format}


def path_for(identifier):
    return VOICES / (slug(identifier, 'voice') + '.json')


def exists(identifier):
    return path_for(identifier).is_file()


def get(identifier):
    document = read_json(path_for(identifier))
    if not document:
        raise CyToolError('NotFound', 'Unknown voice: ' + str(identifier))
    return normalize_stable_voice(document)


def listing(persona_id=''):
    items = []
    if not VOICES.is_dir():
        return items
    for item in sorted(VOICES.glob('*.json')):
        document = read_json(item)
        if not document:
            continue
        if persona_id and document.get('persona_id') != persona_id:
            continue
        reference = Path(document.get('reference_audio', ''))
        items.append({'id': document.get('id', item.stem), 'name': document.get('name', item.stem),
                      'persona_id': document.get('persona_id', ''),
                      'model': document.get('model', ''), 'source': document.get('source', ''),
                      'seconds': document.get('reference_seconds', 0.0),
                      'locked': bool(document.get('locked')),
                      'created': document.get('created', ''),
                      'reference_audio': str(reference),
                      'reference_text': document.get('reference_text', ''),
                      'description': document.get('description', ''),
                      'language': document.get('language', 'Auto'),
                      'available': reference.is_file()})
    return items


def create(name, audio, transcript, *, persona_id='', model='1.7B-Base',
           backend='qwen3tts', source='generated', language='Auto', description='',
           notes='', seed=-1, identifier=''):
    """Register a take as a reusable voice. The recording is copied next to the document."""
    audio = Path(audio)
    if not audio.is_file():
        raise CyToolError('MissingInput', 'Reference recording not found: ' + str(audio))
    details = probe(audio)
    low, high = ACCEPTED_SECONDS
    if not low <= details['seconds'] <= high:
        raise CyToolError(
            'InvalidInput',
            'A reference of %.1f s cannot be used; keep it between %.0f and %.0f seconds '
            '(%.0f to %.0f works best).'
            % (details['seconds'], low, high, IDEAL_SECONDS[0], IDEAL_SECONDS[1]))
    transcript = (transcript or '').strip()
    if not transcript:
        raise CyToolError('InvalidParameters',
                          'A cloned voice needs the exact words of its reference. Transcribe the '
                          'take first, or type what is said in it.')

    VOICES.mkdir(parents=True, exist_ok=True)
    base = slug(identifier or name, 'voice')
    candidate = base
    while exists(candidate):
        candidate = base + '-' + time.strftime('%H%M%S')
    stored = VOICES / (candidate + audio.suffix.lower())
    if audio.resolve() != stored.resolve():
        shutil.copyfile(audio, stored)

    document = normalize_stable_voice({
        'id': candidate, 'name': name or candidate, 'persona_id': persona_id,
        'backend': backend, 'model': model, 'reference_audio': str(stored),
        'reference_text': transcript, 'reference_seconds': round(details['seconds'], 3),
        'reference_sha256': _digest(stored), 'source': source, 'description': description,
        'language': language, 'seed': int(seed), 'locked': True, 'created': now(),
        'notes': notes,
    })
    write_json(path_for(candidate), document)
    return document


def update(document):
    """Save an edited voice. A locked voice refuses a change of reference or model."""
    document = normalize_stable_voice(document)
    identifier = document.get('id', '')
    previous = read_json(path_for(identifier))
    if not previous:
        raise CyToolError('NotFound', 'Unknown voice: ' + str(identifier))
    if previous.get('locked'):
        for field in ('reference_audio', 'reference_text', 'model', 'backend'):
            if document.get(field) != previous.get(field):
                raise CyToolError(
                    'Locked',
                    'This voice is locked so that it keeps sounding the same. Unlock it first, '
                    'or create a new voice from a new take.')
    write_json(path_for(identifier), document)
    return document


def verify(identifier):
    """Has the reference recording changed or gone since the voice was created?"""
    document = get(identifier)
    reference = Path(document.get('reference_audio', ''))
    if not reference.is_file():
        return {'id': identifier, 'ok': False, 'reason': 'The reference recording is missing.'}
    if document.get('reference_sha256') and _digest(reference) != document['reference_sha256']:
        return {'id': identifier, 'ok': False,
                'reason': 'The reference recording changed since this voice was created; the '
                          'voice would no longer sound the same.'}
    return {'id': identifier, 'ok': True, 'reason': ''}


def remove(identifier):
    document = path_for(identifier)
    if not document.is_file():
        raise CyToolError('NotFound', 'Unknown voice: ' + str(identifier))
    trash = VOICES / '.trash' / (slug(identifier, 'voice') + '-' + time.strftime('%Y%m%d-%H%M%S'))
    trash.mkdir(parents=True, exist_ok=True)
    stored = read_json(document)
    document.replace(trash / document.name)
    reference = Path(stored.get('reference_audio', ''))
    if reference.is_file() and reference.parent.resolve() == VOICES.resolve():
        reference.replace(trash / reference.name)
    return {'id': identifier, 'trash': str(trash)}


def clone_parameters(document):
    """The worker payload that reproduces this voice."""
    document = normalize_stable_voice(document)
    return {'mode': 'clone', 'reference_audio': document['reference_audio'],
            'reference_text': document['reference_text'], 'model': document['model'],
            'language': document.get('language', 'Auto'),
            'seed': document.get('seed', -1)}
