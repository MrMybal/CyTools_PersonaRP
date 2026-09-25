"""The persistent library: characters and worlds that outlive a conversation.

One JSON document per persona in data/personas, one per world in data/worlds. Each save
bumps `revision` and keeps the previous document under data/personas/<id>.revisions, so a
character can evolve without losing what it used to be. Nothing here is ever deleted by a
routine operation: `remove` moves a document to a .trash folder.
"""
import copy
import hashlib
import json
import re
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path

from cytools_core import CyToolError

from .paths import PERSONAS, WORLDS, EXPORTS, VOICES, read_json, write_json
from .schemas import (FORMAT_BUNDLE, FORMAT_PERSONA, FORMAT_WORLD, SCHEMA_VERSION,
                      normalize_persona, normalize_world, normalize_stable_voice)

MAX_REVISIONS = 50


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def slug(name, fallback='persona'):
    # Accents are folded rather than dropped: « Maëlis » gives maelis, not ma-lis.
    folded = ''.join(character for character in unicodedata.normalize('NFKD', str(name or ''))
                     if not unicodedata.combining(character))
    value = re.sub(r'[^a-z0-9]+', '-', folded.lower()).strip('-')
    return value[:48] or fallback


def new_id(name, folder, fallback='persona'):
    """Readable identifier, unique inside its folder; the suffix only appears on a clash."""
    base = slug(name, fallback)
    candidate = base
    while (folder / (candidate + '.json')).exists():
        candidate = base + '-' + uuid.uuid4().hex[:6]
    return candidate


def _safe(identifier):
    if not identifier or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', str(identifier)):
        raise CyToolError('InvalidParameters', 'Invalid identifier: ' + repr(identifier))
    return str(identifier)


class Collection:
    """A folder of JSON documents of one kind, with revisions and a trash."""

    def __init__(self, folder, normalize, document_format, fallback):
        self.folder = folder
        self.normalize = normalize
        self.format = document_format
        self.fallback = fallback

    def path(self, identifier):
        return self.folder / (_safe(identifier) + '.json')

    def exists(self, identifier):
        return self.path(identifier).is_file()

    def ids(self):
        if not self.folder.is_dir():
            return []
        return sorted(p.stem for p in self.folder.glob('*.json'))

    def list(self):
        items = []
        for identifier in self.ids():
            document = read_json(self.path(identifier))
            if document:
                items.append({'id': identifier, 'name': document.get('name', identifier),
                              'summary': document.get('summary', ''),
                              'world_id': document.get('world_id', ''),
                              'revision': document.get('revision', 0),
                              'modified': document.get('modified', '')})
        return items

    def get(self, identifier):
        document = read_json(self.path(identifier))
        if not document:
            raise CyToolError('NotFound', 'Unknown ' + self.fallback + ': ' + str(identifier))
        return self.normalize(document)

    def create(self, document=None):
        value = self.normalize(document or {})
        self.folder.mkdir(parents=True, exist_ok=True)
        value['id'] = new_id(value.get('name'), self.folder, self.fallback)
        value['format'] = self.format
        value['schemaVersion'] = SCHEMA_VERSION
        value['created'] = value['modified'] = now()
        value['revision'] = 1
        write_json(self.path(value['id']), value)
        return value

    def save(self, document):
        """Write a new revision. The previous document is kept, not overwritten in place."""
        value = self.normalize(document)
        identifier = _safe(value.get('id') or '')
        previous = read_json(self.path(identifier))
        if not previous:
            raise CyToolError('NotFound', 'Unknown ' + self.fallback + ': ' + identifier)
        value['format'] = self.format
        value['schemaVersion'] = SCHEMA_VERSION
        value['created'] = previous.get('created') or now()
        value['modified'] = now()
        value['revision'] = int(previous.get('revision', 0)) + 1
        self._archive(identifier, previous)
        write_json(self.path(identifier), value)
        return value

    def _archive(self, identifier, previous):
        folder = self.folder / (identifier + '.revisions')
        write_json(folder / ('%05d.json' % int(previous.get('revision', 0))), previous)
        kept = sorted(folder.glob('*.json'))
        for stale in kept[:-MAX_REVISIONS]:
            stale.unlink(missing_ok=True)

    def revisions(self, identifier):
        folder = self.folder / (_safe(identifier) + '.revisions')
        if not folder.is_dir():
            return []
        return [{'revision': int(p.stem), 'path': str(p)} for p in sorted(folder.glob('*.json'))]

    def restore(self, identifier, revision):
        folder = self.folder / (_safe(identifier) + '.revisions')
        source = folder / ('%05d.json' % int(revision))
        if not source.is_file():
            raise CyToolError('NotFound', 'Unknown revision %s for %s' % (revision, identifier))
        document = self.normalize(read_json(source))
        document['id'] = identifier
        return self.save(document)

    def duplicate(self, identifier, name=''):
        document = self.get(identifier)
        document['name'] = name or (document.get('name', identifier) + ' (copy)')
        document.pop('id', None)
        return self.create(document)

    def remove(self, identifier):
        """Never a delete: the document and its revisions move to .trash."""
        identifier = _safe(identifier)
        source = self.path(identifier)
        if not source.is_file():
            raise CyToolError('NotFound', 'Unknown ' + self.fallback + ': ' + identifier)
        trash = self.folder / '.trash' / (identifier + '-' + time.strftime('%Y%m%d-%H%M%S'))
        trash.mkdir(parents=True, exist_ok=True)
        source.replace(trash / (identifier + '.json'))
        revisions = self.folder / (identifier + '.revisions')
        if revisions.is_dir():
            revisions.replace(trash / 'revisions')
        return {'id': identifier, 'trash': str(trash)}


personas = Collection(PERSONAS, normalize_persona, FORMAT_PERSONA, 'persona')
worlds = Collection(WORLDS, normalize_world, FORMAT_WORLD, 'world')


# ------------------------------------------------------------------ relationships

def relation_targets(persona):
    return {item.get('persona_id'): item for item in persona.get('relationships', []) if item.get('persona_id')}


def set_relation(persona, relation, reciprocal=None):
    """Upsert a bond on a sheet, and optionally write the mirror bond on the other sheet."""
    relation = copy.deepcopy(relation)
    target = relation.get('persona_id', '')
    if target and target == persona.get('id'):
        raise CyToolError('InvalidParameters', 'A character cannot hold a relationship to itself.')
    if target and not relation.get('name') and personas.exists(target):
        relation['name'] = personas.get(target).get('name', target)
    items = [item for item in persona.get('relationships', []) if item.get('persona_id') != target]
    items.append(relation)
    persona['relationships'] = items
    saved = personas.save(persona)
    if reciprocal is not None and target and personas.exists(target):
        other = personas.get(target)
        mirror = copy.deepcopy(reciprocal)
        mirror['persona_id'] = saved['id']
        mirror.setdefault('name', saved.get('name', saved['id']))
        others = [item for item in other.get('relationships', []) if item.get('persona_id') != saved['id']]
        others.append(mirror)
        other['relationships'] = others
        personas.save(other)
    return saved


def drop_relation(persona, target, both=False):
    persona['relationships'] = [item for item in persona.get('relationships', [])
                                if item.get('persona_id') != target]
    saved = personas.save(persona)
    if both and target and personas.exists(target):
        other = personas.get(target)
        other['relationships'] = [item for item in other.get('relationships', [])
                                  if item.get('persona_id') != saved['id']]
        personas.save(other)
    return saved


def cast(world_id):
    """Every character sharing a world — the cast a scene can draw from."""
    members = []
    for entry in personas.list():
        if not world_id or entry.get('world_id') == world_id:
            members.append(entry)
    return members


# ------------------------------------------------------------------ export/import

def voice_ids(persona):
    """Every stable voice a sheet speaks with: its own, then one per configured language."""
    voice = persona.get('voice') or {}
    found = [voice.get('voice_id', '')]
    found += [entry.get('voice_id', '') for entry in voice.get('languages') or []
              if entry.get('source') == 'voice']
    return [identifier for position, identifier in enumerate(found)
            if identifier and identifier not in found[:position]]


def _voice_documents(persona):
    """The voices a character needs to sound the same elsewhere — the per-language ones too,
    or an exported character would come back speaking English with its French voice."""
    documents = []
    for voice_id in voice_ids(persona):
        document = read_json(VOICES / (slug(voice_id, 'voice') + '.json'))
        if document:
            documents.append(normalize_stable_voice(document))
    return documents


def build_bundle(persona_ids, include_world=True, include_voice=True):
    """A self-contained document: the sheets, their world, and their voice descriptors."""
    sheets = [personas.get(identifier) for identifier in persona_ids]
    bundle = {'format': FORMAT_BUNDLE, 'schemaVersion': SCHEMA_VERSION, 'exported': now(),
              'personas': sheets, 'worlds': [], 'voices': []}
    if include_world:
        seen = []
        for sheet in sheets:
            world_id = sheet.get('world_id')
            if world_id and world_id not in seen and worlds.exists(world_id):
                seen.append(world_id)
                bundle['worlds'].append(worlds.get(world_id))
    if include_voice:
        for sheet in sheets:
            for document in _voice_documents(sheet):
                if all(document['id'] != other['id'] for other in bundle['voices']):
                    bundle['voices'].append(document)
    return bundle


def export_bundle(persona_ids, destination='', include_world=True, include_voice=True,
                  include_audio=False, include_images=True):
    """Write the bundle.

    Reference takes and photographs are real files, so as soon as either is included the
    result is a .zip rather than a bare JSON document.
    """
    bundle = build_bundle(persona_ids, include_world, include_voice)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    stem = slug(bundle['personas'][0].get('name'), 'personas') if len(bundle['personas']) == 1 else 'personas'
    stem += '-' + time.strftime('%Y%m%d-%H%M%S')
    audio = []
    if include_audio:
        for voice in bundle['voices']:
            source = Path(voice.get('reference_audio', ''))
            if source.is_file():
                audio.append((voice, source))
    pictures = []
    if include_images:
        from . import imaging
        for sheet in bundle['personas']:
            for item, source in imaging.bundled(sheet):
                pictures.append((item, source, 'images/%s/%s' % (sheet['id'], source.name)))
    if audio or pictures:
        target = Path(destination) if destination else EXPORTS / (stem + '.zip')
        target.parent.mkdir(parents=True, exist_ok=True)
        for voice, source in audio:
            voice['reference_audio'] = 'audio/' + source.name
        for item, _, inside in pictures:
            item['file'] = inside
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('persona-bundle.json', json.dumps(bundle, ensure_ascii=False, indent=2))
            for _, source in audio:
                archive.write(source, 'audio/' + source.name)
            for _, source, inside in pictures:
                archive.write(source, inside)
    else:
        target = Path(destination) if destination else EXPORTS / (stem + '.json')
        write_json(target, bundle)
    return {'file': str(target), 'personas': [p['id'] for p in bundle['personas']],
            'worlds': [w['id'] for w in bundle['worlds']],
            'voices': [v['id'] for v in bundle['voices']], 'bundledAudio': len(audio),
            'bundledImages': len(pictures)}


def _read_bundle(path):
    path = Path(path)
    if not path.is_file():
        raise CyToolError('NotFound', 'No such file: ' + str(path))
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if 'persona-bundle.json' not in names:
                raise CyToolError('InvalidParameters', 'Archive does not contain persona-bundle.json.')
            document = json.loads(archive.read('persona-bundle.json').decode('utf-8'))

        # The members are read later, once the sheets are known. Reopening per member keeps
        # the reader valid outside this block instead of holding a closed handle — and keeps
        # a bundle of photographs and takes out of memory.
        def reader(name):
            with zipfile.ZipFile(path) as opened:
                return opened.read(name)

        return document, reader, names
    return read_json(path), None, []


def _restore_images(persona, reader, names):
    """Write the photographs of an imported sheet back to disk beside it."""
    from . import imaging
    restored = []
    folder = imaging.folder(persona['id'])
    for item in persona.get('references') or []:
        inside = item.get('file', '')
        if inside not in names:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / Path(inside).name
        target.write_bytes(reader(inside))
        restored.append({**item, 'file': str(target)})
    return restored


def import_bundle(path, rename=True):
    """Import sheets, worlds and voices. Existing identifiers are never silently replaced."""
    document, reader, names = _read_bundle(path)
    fmt = document.get('format')
    if fmt == FORMAT_PERSONA:
        document = {'format': FORMAT_BUNDLE, 'personas': [document], 'worlds': [], 'voices': []}
    elif fmt == FORMAT_WORLD:
        document = {'format': FORMAT_BUNDLE, 'personas': [], 'worlds': [document], 'voices': []}
    elif fmt != FORMAT_BUNDLE:
        raise CyToolError('InvalidParameters', 'Not a PersonaRP document: ' + str(fmt))

    imported = {'personas': [], 'worlds': [], 'voices': []}
    world_map = {}
    for world in document.get('worlds', []):
        value = normalize_world(world)
        original = value.get('id', '')
        if original and not worlds.exists(original):
            value['format'] = FORMAT_WORLD
            worlds.folder.mkdir(parents=True, exist_ok=True)
            write_json(worlds.path(original), {**value, 'created': value.get('created') or now(),
                                               'modified': now(), 'revision': max(1, value.get('revision', 1))})
            world_map[original] = original
        else:
            if not rename and original:
                raise CyToolError('Conflict', 'World already exists: ' + original)
            created = worlds.create({**value, 'id': ''})
            world_map[original] = created['id']
        imported['worlds'].append(world_map[original])

    persona_map = {}
    for persona in document.get('personas', []):
        value = normalize_persona(persona)
        original = value.get('id', '')
        if reader and value.get('references'):
            value['references'] = _restore_images(value, reader, names)
        if value.get('world_id') in world_map:
            value['world_id'] = world_map[value['world_id']]
        if original and not personas.exists(original):
            personas.folder.mkdir(parents=True, exist_ok=True)
            write_json(personas.path(original), {**value, 'format': FORMAT_PERSONA,
                                                 'created': value.get('created') or now(),
                                                 'modified': now(),
                                                 'revision': max(1, value.get('revision', 1))})
            imported['personas'].append(original)
        else:
            if not rename and original:
                raise CyToolError('Conflict', 'Character already exists: ' + original)
            imported['personas'].append(personas.create({**value, 'id': ''})['id'])
        if original:
            persona_map[original] = imported['personas'][-1]

    # Characters imported together point at each other. When one of them had to take a new
    # identifier, its companions must follow it rather than the sheet that was already there.
    renamed = {old: new for old, new in persona_map.items() if old != new}
    if renamed:
        for identifier in imported['personas']:
            sheet = read_json(personas.path(identifier))
            bonds = sheet.get('relationships') or []
            if any(bond.get('persona_id') in renamed for bond in bonds):
                sheet['relationships'] = [
                    {**bond, 'persona_id': renamed.get(bond.get('persona_id'),
                                                       bond.get('persona_id'))}
                    for bond in bonds]
                write_json(personas.path(identifier), sheet)

    # A voice already in the library is never touched: the same recording is reused, and a
    # different voice under the same name comes in under a new identifier.
    voice_map = {}
    for voice in document.get('voices', []):
        value = normalize_stable_voice(voice)
        original = slug(value.get('id') or value.get('name'), 'voice')
        reference = value.get('reference_audio', '')
        payload = reader(reference) if reader and reference in names else None
        digest = hashlib.sha256(payload).hexdigest() if payload is not None \
            else value.get('reference_sha256', '')
        identifier, present = _voice_identifier(original, digest)
        voice_map[original] = identifier
        if value.get('id'):
            voice_map[value['id']] = identifier
        if present:
            continue
        if payload is not None:
            VOICES.mkdir(parents=True, exist_ok=True)
            audio = VOICES / (identifier + Path(reference).suffix)
            if audio.exists():
                audio = VOICES / ('%s-%s%s' % (identifier, uuid.uuid4().hex[:6],
                                               Path(reference).suffix))
            audio.write_bytes(payload)
            value['reference_audio'] = str(audio)
        value['id'] = identifier
        value['persona_id'] = persona_map.get(value.get('persona_id'), value.get('persona_id', ''))
        write_json(VOICES / (identifier + '.json'), value)
        imported['voices'].append(identifier)

    renamed_voices = {old: new for old, new in voice_map.items() if old != new}
    if renamed_voices:
        for identifier in imported['personas']:
            sheet = read_json(personas.path(identifier))
            voice = sheet.get('voice') or {}
            changed = voice.get('voice_id') in renamed_voices
            voice['voice_id'] = renamed_voices.get(voice.get('voice_id'), voice.get('voice_id', ''))
            for entry in voice.get('languages') or []:
                if entry.get('voice_id') in renamed_voices:
                    entry['voice_id'] = renamed_voices[entry['voice_id']]
                    changed = True
            if changed:
                sheet['voice'] = voice
                write_json(personas.path(identifier), sheet)
    return imported


def _voice_identifier(original, digest):
    """Where a bundled voice goes: (identifier, already present with the same recording)."""
    identifier, number = original, 1
    while True:
        existing = read_json(VOICES / (identifier + '.json'))
        if not existing:
            return identifier, False
        if digest and existing.get('reference_sha256') == digest:
            return identifier, True
        number += 1
        identifier = '%s-%d' % (original, number)
