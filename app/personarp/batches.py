"""Voice batches: a list of lines in, a folder of takes out.

A batch — a task — is given as a script, a CSV or a JSON list: who says what, optionally
with an identifier, a language and a file name. It can bring its own characters: complete
bundles exported by PersonaRP (sheet, world, stable voices and their recordings, the
per-language voices included), copied into the task and never into the library. Each task
gets its own folder in data/batches:

    <name>-<date>/
        personnages/      the characters the task brought: fiches/, mondes/, voix-stables/
        lot.json          the batch as it was understood: every line, its id, its speaker
        source.<ext>      the list that was given, untouched
        voix/             one WAV per line, named after its id
        resultats.json    what happened to each line: file, duration, voice used, or error
        resultats.csv     the same, for a spreadsheet

A batch can be resumed: lines already written are not generated again, which matters when
the machine is paid by the hour.
"""
import csv
import hashlib
import io
import json
import re
import time
import unicodedata
from pathlib import Path

from cytools_core import CyToolError

from . import library
from .paths import BATCHES, read_json, write_json
from .schemas import (FORMAT_BUNDLE, FORMAT_PERSONA, FORMAT_WORLD, normalize_persona,
                      normalize_stable_voice, normalize_world)

MAX_LINES = 5000
MAX_TEXT = 4000
FIELDS = {
    'id': ('id', 'identifiant', 'identifier', 'ref', 'reference', 'référence', 'code'),
    'character': ('character', 'personnage', 'persona', 'persona_id', 'speaker', 'nom', 'name'),
    'voice': ('voice', 'voix', 'voice_id'),
    'text': ('text', 'texte', 'line', 'réplique', 'replique', 'dialogue'),
    'language': ('language', 'langue', 'lang'),
    'file': ('file', 'fichier', 'filename', 'nom_fichier'),
}


def fold(value):
    """Case- and accent-insensitive form of a name."""
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(character for character in value if not unicodedata.combining(character))
    return re.sub(r'\s+', ' ', value).strip().casefold()


def _field(row, name):
    for key in FIELDS[name]:
        for candidate, value in row.items():
            if fold(candidate) == fold(key) and str(value or '').strip():
                return str(value).strip()
    return ''


def _normalize(rows):
    lines = []
    for row in rows:
        if not isinstance(row, dict):
            raise CyToolError('InvalidInput', 'Each line of a batch must be an object.')
        line = {name: _field(row, name) for name in FIELDS}
        if line['text']:
            lines.append(line)
    return lines


def parse_script(text):
    """`Name: line` per line, or `ID | Name: line` to give the line its identifier.

    A line without a speaker continues the previous one; a line starting with # is a comment.
    """
    lines = []
    for raw in (text or '').splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            continue
        identifier = ''
        tagged = re.match(r'^([A-Za-z0-9][A-Za-z0-9._\-]{0,79})\s*\|\s*(.+)$', stripped)
        if tagged:
            identifier, stripped = tagged.group(1), tagged.group(2).strip()
        match = re.match(r'^([^:]{1,80}?)\s*:\s*(.+)$', stripped)
        if match and not re.match(r'^\[', stripped):
            lines.append({'id': identifier, 'character': match.group(1).strip(), 'voice': '',
                          'text': match.group(2).strip(), 'language': '', 'file': ''})
        elif identifier:
            raise CyToolError('InvalidInput', 'Line "%s" has an identifier but no speaker: '
                              '"ID | Name: text".' % identifier)
        elif lines:
            lines[-1]['text'] += ' ' + stripped
        else:
            raise CyToolError('InvalidInput',
                              'The first line of a script must name its speaker: "Name: text".')
    return lines


def parse_csv(text):
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=';,\t').delimiter
    except csv.Error:
        delimiter = ';' if sample.count(';') >= sample.count(',') else ','
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return []
    header = [fold(cell) for cell in rows[0]]
    known = {fold(key) for keys in FIELDS.values() for key in keys}
    if any(cell in known for cell in header):
        return _normalize([dict(zip(rows[0], row)) for row in rows[1:]])
    # No header: speaker, text[, language[, file]].
    order = ('character', 'text', 'language', 'file')
    return _normalize([{name: row[index] for index, name in enumerate(order) if index < len(row)}
                       for row in rows])


def parse_json(text):
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise CyToolError('InvalidInput', 'The batch is not valid JSON: %s' % exc)
    rows = document if isinstance(document, list) else \
        document.get('items') or document.get('lines') or document.get('lignes') or [] \
        if isinstance(document, dict) else None
    if rows is None:
        raise CyToolError('InvalidInput', 'A JSON batch is a list of lines, or {"lines": [...]}.')
    return _normalize(rows)


def guess_format(text):
    """json, csv or script, from the text itself — a script never looks like the others."""
    stripped = (text or '').lstrip('﻿ \t\r\n')
    if stripped[:1] in ('[', '{'):
        return 'json'
    first = next((line for line in stripped.splitlines()
                  if line.strip() and not line.lstrip().startswith('#')), '')
    known = {fold(key) for keys in FIELDS.values() for key in keys}
    for delimiter in (';', '\t', ','):
        cells = [fold(cell).strip('"') for cell in first.split(delimiter)]
        if len(cells) >= 2 and any(cell in known for cell in cells):
            return 'csv'
    return 'script'


def parse_text(text, format='auto'):
    format = guess_format(text) if format in ('', 'auto') else format
    if format == 'json':
        return parse_json(text)
    if format == 'csv':
        return parse_csv(text)
    return parse_script(text)


def parse_file(path):
    path = Path(path)
    if not path.is_file():
        raise CyToolError('MissingInput', 'Batch file not found: ' + str(path))
    text = path.read_text(encoding='utf-8-sig')
    suffix = path.suffix.lower()
    if suffix == '.json':
        return parse_json(text)
    if suffix in ('.csv', '.tsv'):
        return parse_csv(text)
    return parse_text(text)


def parse(file='', text='', items=None, format='auto'):
    if items:
        lines = _normalize(items)
    elif file:
        lines = parse_file(file)
    elif (text or '').strip():
        lines = parse_text(text, format)
    else:
        raise CyToolError('InvalidParameters', 'Give a batch: a file, a script text or items.')
    if not lines:
        raise CyToolError('InvalidInput', 'The batch has no line to speak.')
    if len(lines) > MAX_LINES:
        raise CyToolError('InvalidInput', 'A batch holds at most %d lines.' % MAX_LINES)
    for number, line in enumerate(lines, 1):
        if len(line['text']) > MAX_TEXT:
            raise CyToolError('InvalidInput', 'Line %d is longer than %d characters.'
                              % (number, MAX_TEXT))
    return lines


def _words(value):
    return [word for word in re.split(r"[\s'’\-.,]+", fold(value)) if word]


def _contains(words, wanted):
    """Do the words of `wanted` appear together, in order, among `words`?"""
    size = len(wanted)
    return size > 0 and any(words[start:start + size] == wanted
                            for start in range(len(words) - size + 1))


class Cast:
    """Finds a character by identifier, name or alias, or by a part of its name that only it
    has: "Vasric" finds "Sire Vasric d'Aubrecourt", "Maëlis" finds "Maëlis de Corvanne".

    The characters a task brought are searched first; the library only after, and only when
    the task allows it. A name that is ambiguous among the task's own characters is reported
    rather than looked up elsewhere.
    """

    def __init__(self, task_sheets=None, use_library=True):
        self.task = list(task_sheets or [])
        self.use_library = use_library
        self.library = [library.personas.get(entry['id']) for entry in library.personas.list()] \
            if use_library else []

    def locate(self, name):
        """(sheet, 'task' | 'library' | '', reason)."""
        if not fold(name):
            return None, '', ''
        for pool, source in ((self.task, 'task'), (self.library, 'library')):
            found, reason = self._search(pool, name)
            if found is not None or reason:
                return found, source if found is not None else '', reason
        return None, '', 'No character called "%s".' % name

    def find(self, name):
        found, _, reason = self.locate(name)
        return found, reason

    @staticmethod
    def _search(sheets, name):
        """In one pool: (sheet, '') when found, (None, reason) when ambiguous, (None, '')."""
        wanted = fold(name)
        exact = [sheet for sheet in sheets
                 if wanted in {fold(sheet['id']), fold(sheet['name'])}
                 | {fold(alias) for alias in sheet.get('aliases') or []}]
        if len(exact) == 1:
            return exact[0], ''
        if len(exact) > 1:
            return None, 'Several characters are called "%s".' % name
        pieces = _words(name)
        partial = [sheet for sheet in sheets
                   if any(_contains(_words(label), pieces)
                          for label in [sheet['name']] + list(sheet.get('aliases') or []))]
        if len(partial) == 1:
            return partial[0], ''
        if len(partial) > 1:
            return None, 'Ambiguous name "%s": it could be %s.' % (
                name, ', '.join(sheet['name'] for sheet in partial[:4]))
        return None, ''


RESERVED = {'con', 'prn', 'aux', 'nul'} | {'com%d' % n for n in range(1, 10)} \
    | {'lpt%d' % n for n in range(1, 10)}


def safe_name(value):
    """A file name that keeps an identifier readable: SC01_L005 stays SC01_L005."""
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r'[^A-Za-z0-9._-]+', '-', value).strip('.-')[:120]
    if value.split('.')[0].casefold() in RESERVED:
        value = '_' + value
    return value


def file_stem(index, line, used):
    """The line's file name: the one asked for, else its id, else 0007-maelis-de-corvanne.
    Never twice the same, whatever the case (Windows does not tell SC01 from sc01)."""
    wanted = safe_name(line.get('file') or line.get('givenId') or '')
    stem = wanted or '%04d-%s' % (index, library.slug(line.get('speakerId') or line.get('character')
                                                      or line.get('voice') or 'voix', 'voix'))
    candidate, number = stem, 1
    while candidate.casefold() in used:
        number += 1
        candidate = '%s-%d' % (stem, number)
    used.add(candidate.casefold())
    return candidate


def assign_ids(lines):
    """Every line gets an identifier: its own when the list gave one, else its number.

    Returns {position: reason} for the lines whose identifier is already taken — those are
    reported, not spoken, since two takes cannot answer to one id.
    """
    taken, duplicates = {}, {}
    for position, line in enumerate(lines):
        given = (line.get('id') or '').strip()
        line['givenId'] = given
        if given:
            if given.casefold() in taken:
                duplicates[position] = 'Id already used by another line: %s (line %d)' % (
                    given, taken[given.casefold()] + 1)
            else:
                taken[given.casefold()] = position
    for position, line in enumerate(lines):
        if not line['givenId']:
            candidate, number = '%04d' % (position + 1), 1
            while candidate.casefold() in taken:
                number += 1
                candidate = '%04d-%d' % (position + 1, number)
            taken[candidate.casefold()] = position
            line['id'] = candidate
    return duplicates


# ------------------------------------------------------------------ a task's own characters

def _digest(path=None, payload=None):
    if payload is not None:
        return hashlib.sha256(payload).hexdigest()
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _task_folders(folder):
    root = Path(folder) / 'personnages'
    return root, root / 'fiches', root / 'mondes', root / 'voix-stables'


def _free(identifier, directory, suffix='.json'):
    candidate, number = identifier, 1
    while (directory / (candidate + suffix)).exists():
        number += 1
        candidate = '%s-%d' % (identifier, number)
    return candidate


def import_task_personas(folder, paths):
    """Copy complete characters into a task: sheets, worlds, stable voices and recordings.

    The library is never written. Within the task, an identifier already taken gets a new
    one and the sheets follow it; a voice whose recording does not match its fingerprint,
    or that comes without its recording, is refused and reported.
    """
    root, sheets_dir, worlds_dir, voices_dir = _task_folders(folder)
    for directory in (sheets_dir, worlds_dir, voices_dir):
        directory.mkdir(parents=True, exist_ok=True)
    summary = read_json(root / 'import.json') or {'sources': [], 'problems': []}
    for path in paths:
        path = Path(path)
        document, reader, names = library._read_bundle(path)
        kind = document.get('format')
        if kind == FORMAT_PERSONA:
            document = {'personas': [document], 'worlds': [], 'voices': []}
        elif kind == FORMAT_WORLD:
            document = {'personas': [], 'worlds': [document], 'voices': []}
        elif kind != FORMAT_BUNDLE:
            raise CyToolError('InvalidInput', '%s is not a PersonaRP character bundle.' % path.name)
        source = {'file': path.name, 'sha256': _digest(path), 'personas': [], 'worlds': [],
                  'voices': []}

        world_map = {}
        for world in document.get('worlds', []):
            value = normalize_world(world)
            original = value.get('id') or library.slug(value.get('name'), 'monde')
            identifier = _free(original, worlds_dir)
            write_json(worlds_dir / (identifier + '.json'), {**value, 'id': identifier})
            world_map[original] = identifier
            source['worlds'].append(identifier)

        voice_map = {}
        for voice in document.get('voices', []):
            value = normalize_stable_voice(voice)
            original = value.get('id') or library.slug(value.get('name'), 'voice')
            reference = value.get('reference_audio', '')
            if not reader or reference not in names:
                summary['problems'].append(
                    'Voice left out, it came without its recording (export the character with '
                    'its recordings): %s (%s)' % (original, path.name))
                continue
            payload = reader(reference)
            digest = _digest(payload=payload)
            if value.get('reference_sha256') and value['reference_sha256'] != digest:
                summary['problems'].append(
                    'Voice left out, its recording does not match its fingerprint: %s (%s)'
                    % (original, path.name))
                continue
            existing = read_json(voices_dir / (original + '.json'))
            if existing and existing.get('reference_sha256') == digest:
                voice_map[original] = original
                continue
            identifier = _free(original, voices_dir)
            audio = identifier + (Path(reference).suffix.lower() or '.wav')
            (voices_dir / audio).write_bytes(payload)
            write_json(voices_dir / (identifier + '.json'),
                       {**value, 'id': identifier, 'reference_audio': audio,
                        'reference_sha256': digest})
            voice_map[original] = identifier
            source['voices'].append(identifier)

        persona_map, sheets = {}, []
        for persona in document.get('personas', []):
            value = normalize_persona(persona)
            original = value.get('id') or library.slug(value.get('name'), 'persona')
            identifier = _free(original, sheets_dir)
            persona_map[original] = identifier
            value['id'] = identifier
            value['world_id'] = world_map.get(value.get('world_id'), value.get('world_id', ''))
            voice = value.get('voice') or {}
            voice['voice_id'] = voice_map.get(voice.get('voice_id'), voice.get('voice_id', ''))
            for entry in voice.get('languages') or []:
                entry['voice_id'] = voice_map.get(entry.get('voice_id'), entry.get('voice_id', ''))
            value['references'] = []              # photographs stay in the bundle
            sheets.append(value)
        for value in sheets:
            value['relationships'] = [
                {**bond, 'persona_id': persona_map.get(bond.get('persona_id'),
                                                       bond.get('persona_id'))}
                for bond in value.get('relationships') or []]
            write_json(sheets_dir / (value['id'] + '.json'), value)
            source['personas'].append(value['id'])
        summary['sources'].append(source)
    write_json(root / 'import.json', summary)
    return summary


def load_task(folder):
    """What a task brought: {'sheets', 'worlds', 'voices', 'problems'}.

    The voices are checked against their fingerprint every time, so a recording changed
    since the import is never used as if it were the same voice.
    """
    root, sheets_dir, worlds_dir, voices_dir = _task_folders(folder)
    task = {'sheets': {}, 'worlds': {}, 'voices': {},
            'problems': list((read_json(root / 'import.json') or {}).get('problems', []))}
    if not root.is_dir():
        return task
    for item in sorted(sheets_dir.glob('*.json')):
        sheet = normalize_persona(read_json(item))
        task['sheets'][sheet['id']] = sheet
    for item in sorted(worlds_dir.glob('*.json')):
        world = normalize_world(read_json(item))
        task['worlds'][world['id']] = world
    for item in sorted(voices_dir.glob('*.json')):
        voice = normalize_stable_voice(read_json(item))
        audio = voices_dir / Path(voice.get('reference_audio', '')).name
        if not audio.is_file():
            task['problems'].append('Voice left out, its recording is missing: ' + voice['id'])
        elif voice.get('reference_sha256') and _digest(audio) != voice['reference_sha256']:
            task['problems'].append('Voice left out, its recording changed since it was '
                                    'imported: ' + voice['id'])
        else:
            task['voices'][voice['id']] = {**voice, 'reference_audio': str(audio)}
    return task


def create_folder(name):
    stamp = time.strftime('%Y%m%d-%H%M%S')
    folder = BATCHES / ('%s-%s' % (library.slug(name or 'lot', 'lot'), stamp))
    number = 1
    while folder.exists():
        number += 1
        folder = BATCHES / ('%s-%s-%d' % (library.slug(name or 'lot', 'lot'), stamp, number))
    (folder / 'voix').mkdir(parents=True)
    return folder


def folder_of(identifier):
    folder = BATCHES / library._safe(identifier)
    if not (folder / 'lot.json').is_file():
        raise CyToolError('NotFound', 'Unknown batch: ' + str(identifier))
    return folder


def write_results(folder, lines):
    ok = sum(1 for line in lines if line.get('status') == 'ok')
    failed = sum(1 for line in lines if line.get('status') == 'error')
    document = {'lines': lines, 'summary': {'lines': len(lines), 'done': ok, 'failed': failed,
                                            'pending': len(lines) - ok - failed,
                                            'updated': library.now()}}
    write_json(folder / 'resultats.json', document)
    columns = ('index', 'id', 'status', 'character', 'speakerName', 'voiceUsed', 'languageUsed',
               'file', 'durationSeconds', 'mode', 'text', 'error')
    with open(folder / 'resultats.csv', 'w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle, delimiter=';')
        writer.writerow(columns)
        for line in lines:
            writer.writerow([line.get(column, '') for column in columns])
    return document['summary']


def listing():
    items = []
    if not BATCHES.is_dir():
        return items
    for folder in sorted(BATCHES.iterdir(), reverse=True):
        batch = read_json(folder / 'lot.json')
        if not batch:
            continue
        summary = (read_json(folder / 'resultats.json') or {}).get('summary') or {}
        items.append({'id': folder.name, 'name': batch.get('name', folder.name),
                      'created': batch.get('created', ''), 'folder': str(folder),
                      'lines': len(batch.get('lines') or []), 'done': summary.get('done', 0),
                      'failed': summary.get('failed', 0),
                      'complete': summary.get('done', 0) == len(batch.get('lines') or [])})
    return items
