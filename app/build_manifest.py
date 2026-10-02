"""Generate app/CyTool.json from the Python schemas, so the manifest cannot drift.

Run: runtime/python/Scripts/python.exe app/build_manifest.py
The manifest is the portable contract read by the CLI, MCP and the interface; writing it by
hand next to schemas.py would guarantee the two disagree eventually.
"""
import json
from pathlib import Path

from personarp.schemas import (LANGUAGES, PERSONA_SCHEMA, RELATION_SCHEMA, SCENE_SCHEMA,
                               STABLE_VOICE_SCHEMA, VOICE_SCHEMA, WORLD_SCHEMA)
from personarp.authoring import PERSONA_TARGETS, WORLD_TARGETS

APP = Path(__file__).resolve().parent
VERSION = '0.1.1'

STR = {'type': 'string'}
BOOL = {'type': 'boolean'}
NUM = {'type': 'number'}
INT = {'type': 'integer'}
ANY_OBJECT = {'type': 'object'}


def text(title, default='', limit=200000, kind=''):
    spec = {'type': 'string', 'default': default, 'title': title, 'maxLength': limit}
    if kind:
        spec['x-cy-kind'] = kind
    return spec


def ident(title, default=''):
    return {'type': 'string', 'default': default, 'title': title, 'maxLength': 80,
            'pattern': '^$|^[a-z0-9][a-z0-9-]{0,79}$'}


def op(identifier, name, description, properties, required, output, **flags):
    operation = {
        'id': identifier, 'name': name, 'description': description,
        'inputSchema': {'type': 'object', 'additionalProperties': False,
                        'properties': properties, 'required': required},
        'outputSchema': {'type': 'object', 'additionalProperties': True, 'properties': output},
        'supportedBackends': flags.pop('backends', []),
        'permissions': flags.pop('permissions', []),
        'canRunAsync': flags.pop('async_', True),
        'canCancel': flags.pop('cancel', True),
        'supportsProgress': flags.pop('progress', False),
    }
    if 'resources' in flags:
        operation['resourceRequirements'] = flags.pop('resources')
    operation.update(flags)
    return operation


# '' means the character's own language: the one its lines were written in.
SPOKEN_LANGUAGE = {'type': 'string', 'enum': [''] + LANGUAGES, 'default': '',
                   'title': 'Language spoken',
                   'description': 'Empty speaks in the character\'s own language. Another language '
                                  'uses the sheet\'s entry for it under voice.languages: the same '
                                  'voice with or without its accent, another stable voice, an '
                                  'invented voice or a preset speaker.'}
VOICE_PLAN = {'type': 'object', 'title': 'Voice really used',
              'properties': {'language': STR, 'native': STR, 'configured': BOOL, 'source': STR,
                             'accent': STR, 'voice_id': STR, 'speaker': STR, 'mode': STR}}
TAKE_TARGET = {'persona_id': ident('Character'),
               'session_id': text('Session', '', 80),
               'turn': {'type': 'integer', 'minimum': 0, 'title': 'Line number in the session'},
               'language': SPOKEN_LANGUAGE,
               'take': {'type': 'integer', 'minimum': 0, 'title': 'Take, from 0 (oldest)'}}
TAKE_OUT = {'audio': {'type': ['object', 'null']}, 'takes': {'type': 'array', 'items': ANY_OBJECT},
            'chosen': INT}

def optional(spec, **extra):
    """An object parameter that may be left out.

    Validation fills a missing parameter with its default, and every schema here defaults to
    {} — which the validator then expands into a complete, empty document. An optional sheet,
    bond or voice override must stay absent when nobody sent it, or it silently replaces the
    real one: a blank mirror bond overwrote the other character's bond, and a blank voice
    override replaced the character's stable voice with a preset speaker.
    """
    value = {key: item for key, item in spec.items() if key != 'default'}
    value.update(extra)
    return value


def partial(spec, **extra):
    """An override: only the fields actually given replace the stored ones."""
    value = optional(spec, **extra)
    value['properties'] = {name: {key: item for key, item in field.items() if key != 'default'}
                           for name, field in spec['properties'].items()}
    return value


BATCH_ABOUT = (
    'The folder holds the list as given (source.*), the batch as understood (lot.json), one WAV '
    'per line in voix/, and resultats.json / resultats.csv. The lines are generated many at a '
    'time in one copy of the voice model; with batch_size 0 the number follows the free VRAM, '
    'and a batch that does not fit is halved and tried again, so a large GPU is used to the '
    'full. A speaker is found by identifier, name, alias or a part of its name no other '
    'character has; voice names a stable voice instead, or on top of the character. A line '
    'that cannot be spoken is reported and the batch goes on. dry_run checks the list — '
    'speakers, voices, languages — before paying for it.')
BATCH_LIST = {
    'text': text('Script', '', 400000, 'MultilineString'),
    'format': {'type': 'string', 'enum': ['auto', 'script', 'csv', 'json'], 'default': 'auto',
               'title': 'What text holds'},
    'items': {'type': 'array', 'maxItems': 5000, 'title': 'Lines',
              'items': {'type': 'object', 'additionalProperties': False, 'properties': {
                  'id': text('Line id', '', 120),
                  'character': text('Character', '', 120),
                  'voice': text('Stable voice', '', 120),
                  'text': text('Line', '', 4000, 'MultilineString'),
                  'language': {'type': 'string', 'enum': [''] + LANGUAGES},
                  'file': text('File name', '', 120)}, 'required': ['text']}},
}
BATCH_OPTIONS = {
    'name': text('Batch name', '', 80),
    'language': dict(SPOKEN_LANGUAGE, description='For every line that does not give its own. '
                     'Empty speaks each character in its own language.'),
    'device': {'type': 'string', 'enum': ['cuda', 'cpu'], 'default': 'cuda'},
    'batch_size': {'type': 'integer', 'minimum': 0, 'maximum': 64, 'default': 0,
                   'title': 'Lines at a time', 'description': '0 sizes the batches to the free VRAM.'},
    'seed': {'type': 'integer', 'minimum': 0, 'maximum': 2 ** 31 - 1, 'default': 42},
    'precision': {'type': 'string', 'enum': ['auto', 'bfloat16', 'float16', 'float32'],
                  'default': 'auto', 'title': 'Precision of the voice model',
                  'description': 'auto: bfloat16 on cards that compute it natively (A100, L4, '
                                 'RTX 30/40), float16 on older ones (T4), float32 on the CPU.'},
    'dry_run': {'type': 'boolean', 'default': False, 'title': 'Check only',
                'description': 'Read the list and say who would speak each line with which voice. '
                               'Generates nothing, makes no folder, needs no GPU.'},
}
BATCH_OUT = {
    'batch': STR, 'folder': STR, 'lines': INT, 'done': INT, 'failed': INT, 'skipped': INT,
    'results': STR, 'dryRun': BOOL, 'ready': INT,
    'preview': {'type': 'array', 'items': ANY_OBJECT},
    'groups': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'mode': STR, 'model': STR, 'lines': INT, 'batchSize': INT, 'firstBatchSize': INT,
        'calls': INT, 'memoryRetries': INT, 'passages': INT, 'generationSeconds': NUM,
        'vramPeakBytes': {'type': ['integer', 'null']},
        'freeVramBytes': {'type': ['integer', 'null']},
        'gpuName': {'type': ['string', 'null']},
        'batchSizes': {'type': ['array', 'null'], 'items': INT},
        'perPassageBytes': {'type': ['integer', 'null']},
        'limitBytes': {'type': ['integer', 'null']},
        'precision': {'type': ['string', 'null']}}}},
    'errors': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'index': INT, 'id': STR, 'error': STR}}},
    'personas': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'id': STR, 'name': STR}}},
    'problems': {'type': 'array', 'items': STR},
}

MODEL_OVERRIDES = {
    'llm_model': text('Conversation model', '', 60,),
    'device': {'type': 'string', 'enum': ['', 'cpu', 'cuda'], 'default': '',
               'title': 'Compute device',
               'description': 'Empty keeps the device recorded on the character sheet.'},
    'temperature': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 2, 'default': None},
    'response_length': {'type': ['integer', 'null'], 'minimum': 16, 'maximum': 4096, 'default': None},
    'seed': {'type': ['integer', 'null'], 'minimum': -1, 'maximum': 2 ** 31 - 1, 'default': None},
    'threads': {'type': ['integer', 'null'], 'minimum': 1, 'maximum': 64, 'default': None},
    'keep_loaded': {'type': 'boolean', 'default': False,
                    'title': 'Keep the model in memory between replies'},
}

CHAT_IN = {
    'persona_id': ident('Character'),
    'persona': optional(PERSONA_SCHEMA, title='Inline character sheet',
                        description='Used instead of persona_id when you do not want to store '
                                    'the character. One of the two is required.'),
    'text': text('Your message', '', 24000, 'MultilineString'),
    'session_id': text('Session', '', 80),
    'history': {'type': 'array', 'default': [], 'maxItems': 500, 'title': 'Conversation so far',
                'description': 'Only used when no session_id is given.',
                'items': {'type': 'object', 'additionalProperties': False,
                          'required': ['role', 'content'],
                          'properties': {'role': {'type': 'string', 'enum': ['user', 'assistant']},
                                         'content': {'type': 'string', 'maxLength': 40000}}}},
    'world_id': ident('World override'),
    'include_cast': {'type': 'boolean', 'default': True,
                     'title': 'Tell the character who else lives in this world'},
    'want_scene': {'type': 'string', 'enum': ['auto', 'yes', 'no'], 'default': 'auto',
                   'title': 'Ask for a scene description',
                   'description': 'auto follows the character sheet.'},
    'speak': {'type': 'string', 'enum': ['auto', 'yes', 'no'], 'default': 'auto',
              'title': 'Render the reply as audio'},
    'save': {'type': 'boolean', 'default': True, 'title': 'Append this turn to the session'},
    **MODEL_OVERRIDES,
}

CHAT_OUT = {
    'text': STR, 'dialogue': STR, 'spoken': STR,
    'scene': SCENE_SCHEMA, 'sceneError': STR, 'rawScene': STR,
    'prompts': ANY_OBJECT, 'annotations': {'type': 'array', 'items': ANY_OBJECT},
    'history': {'type': 'array', 'items': ANY_OBJECT}, 'sessionId': STR,
    'audioFile': STR, 'voiceError': STR, 'file': STR, 'sessionFile': STR,
    'context': ANY_OBJECT, 'seconds': NUM, 'reused': BOOL, 'mimeType': STR,
}

AUTHOR_TARGETS = sorted(set(PERSONA_TARGETS) | set(WORLD_TARGETS))

# Filled from data/reports/platform-tested.json, which is written by the acceptance runs.
# An empty list is the honest default: declared is not tested.
TESTED_WINDOWS = json.loads((APP / 'platform-tested.json').read_text('utf-8')) \
    if (APP / 'platform-tested.json').is_file() else []

OPERATIONS = [
    op('chat', 'Talk to a character',
       'Generate an in-character reply. Returns the dialogue, the delivery annotations, and '
       'when the sheet asks for it a scene directive describing appearance, movement and camera '
       'for an image or video tool. The directive is data, never spoken.',
       CHAT_IN, ['text'], CHAT_OUT, progress=True,
       # The conversation model's memory is held by the resident worker, not by the job.
       resources={'ramBytes': 1024 ** 3, 'cpuThreads': 4, 'diskBytes': 256 * 1024 ** 2}),

    op('preview_prompt', 'Preview the assembled prompt',
       'Show exactly what the model will receive for this character, including which sections '
       'did not fit the context budget. Loads nothing.',
       {'persona_id': ident('Character'), 'persona': optional(PERSONA_SCHEMA),
        'text': text('Message', '', 24000, 'MultilineString'),
        'session_id': text('Session', '', 80), 'world_id': ident('World override'),
        'include_cast': {'type': 'boolean', 'default': True}},
       [], {'messages': {'type': 'array', 'items': ANY_OBJECT}, 'prompt': STR,
            'context': ANY_OBJECT, 'file': STR}, cancel=False),

    op('author', 'Ask the assistant for a proposal',
       'Write a character sheet, a world, or one section of either. The assistant never plays '
       'the character and never writes to the library; apply_proposal does that explicitly.',
       {'request': text('What to write', '', 24000, 'MultilineString'),
        'target': {'type': 'string', 'enum': AUTHOR_TARGETS, 'default': 'sheet',
                   'title': 'What to fill'},
        'kind': {'type': 'string', 'enum': ['persona', 'world'], 'default': 'persona'},
        'persona_id': ident('Character used as context'),
        'world_id': ident('World used as context'),
        'thread_id': text('Discussion used as context', '', 80,),
        'image': text('Reference image read as text first', '', 1000, 'Image'),
        'vision_model': text('Vision model used to read it', '', 60),
        'language': text('Language', 'Francais', 60),
        **MODEL_OVERRIDES},
       ['request'],
       {'proposal': {'type': ['object', 'array', 'string']}, 'raw': STR, 'target': STR,
        'kind': STR, 'seconds': NUM, 'picture': ANY_OBJECT, 'file': STR}, progress=True,
       resources={'ramBytes': 1024 ** 3, 'cpuThreads': 4}),

    op('apply_proposal', 'Apply a proposal',
       'Merge a proposal into a stored character or world. Only the targeted section is '
       'replaced; a new revision is written and the previous one is kept.',
       {'persona_id': ident('Character'), 'world_id': ident('World'),
        'target': {'type': 'string', 'enum': AUTHOR_TARGETS, 'default': 'sheet'},
        'kind': {'type': 'string', 'enum': ['persona', 'world'], 'default': 'persona'},
        'proposal': {'type': ['object', 'array', 'string'], 'title': 'Proposal'}},
       ['proposal'], {'document': ANY_OBJECT, 'id': STR, 'revision': INT}, cancel=False),

    # ----------------------------------------------------------------- library
    op('list_personas', 'List characters', 'Every stored character, newest change first.',
       {'world_id': ident('Only this world')}, [],
       {'personas': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('get_persona', 'Read a character', 'The full sheet as stored.',
       {'persona_id': ident('Character')}, ['persona_id'],
       {'persona': PERSONA_SCHEMA, 'world': WORLD_SCHEMA, 'file': STR}, cancel=False),

    op('create_persona', 'Create a character',
       'Create a sheet from the supplied fields; everything omitted takes its default.',
       {'persona': optional(PERSONA_SCHEMA), 'name': text('Name', '', 120)}, [],
       {'persona': PERSONA_SCHEMA, 'id': STR, 'file': STR}, cancel=False),

    op('save_persona', 'Save a character',
       'Write a new revision of an existing sheet. The previous revision is kept.',
       {'persona': PERSONA_SCHEMA}, ['persona'],
       {'persona': PERSONA_SCHEMA, 'id': STR, 'revision': INT, 'file': STR}, cancel=False),

    op('duplicate_persona', 'Duplicate a character', 'Copy a sheet under a new identifier.',
       {'persona_id': ident('Character'), 'name': text('New name', '', 120)}, ['persona_id'],
       {'persona': PERSONA_SCHEMA, 'id': STR}, cancel=False),

    op('remove_persona', 'Remove a character',
       'Move a sheet and its revisions to data/personas/.trash. Nothing is deleted.',
       {'persona_id': ident('Character')}, ['persona_id'],
       {'id': STR, 'trash': STR}, cancel=False),

    op('persona_revisions', 'List revisions', 'Past revisions kept next to a sheet.',
       {'persona_id': ident('Character')}, ['persona_id'],
       {'revisions': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('restore_persona', 'Restore a revision',
       'Bring back a past revision as a new revision, so nothing is lost either way.',
       {'persona_id': ident('Character'), 'revision': {'type': 'integer', 'minimum': 0}},
       ['persona_id', 'revision'], {'persona': PERSONA_SCHEMA, 'revision': INT}, cancel=False),

    op('list_worlds', 'List worlds', 'Every stored world.', {}, [],
       {'worlds': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('get_world', 'Read a world', 'The full world document and its cast.',
       {'world_id': ident('World')}, ['world_id'],
       {'world': WORLD_SCHEMA, 'cast': {'type': 'array', 'items': ANY_OBJECT}, 'file': STR},
       cancel=False),

    op('create_world', 'Create a world', 'Create a shared lore document.',
       {'world': optional(WORLD_SCHEMA), 'name': text('Name', '', 120)}, [],
       {'world': WORLD_SCHEMA, 'id': STR, 'file': STR}, cancel=False),

    op('save_world', 'Save a world', 'Write a new revision of a world.',
       {'world': WORLD_SCHEMA}, ['world'],
       {'world': WORLD_SCHEMA, 'id': STR, 'revision': INT, 'file': STR}, cancel=False),

    op('remove_world', 'Remove a world',
       'Move a world to data/worlds/.trash. Characters keep their world_id.',
       {'world_id': ident('World')}, ['world_id'], {'id': STR, 'trash': STR}, cancel=False),

    op('set_relation', 'Set a relationship',
       'Create or update how one character feels about another, optionally writing the mirror '
       'bond on the other sheet as well.',
       {'persona_id': ident('Character'), 'relation': RELATION_SCHEMA,
        'reciprocal': optional(RELATION_SCHEMA, title='Mirror bond',
                               description='Written on the other sheet when supplied.'),
        'mirror': {'type': 'boolean', 'default': False,
                   'title': 'Also write the mirror bond'}},
       ['persona_id', 'relation'], {'persona': PERSONA_SCHEMA}, cancel=False),

    op('drop_relation', 'Remove a relationship', 'Forget a bond, optionally on both sheets.',
       {'persona_id': ident('Character'), 'target_id': ident('Other character'),
        'both': {'type': 'boolean', 'default': False}},
       ['persona_id', 'target_id'], {'persona': PERSONA_SCHEMA}, cancel=False),

    op('remember', 'Update memory and state',
       'Apply facts, episodes and current state to a character. Memory is always explicit: '
       'nothing is harvested from a conversation without this call.',
       {'persona_id': ident('Character'),
        'facts': {'type': 'array', 'default': [], 'maxItems': 64,
                  'items': {'type': 'string', 'maxLength': 500}, 'title': 'Facts to add'},
        'episodes': {'type': 'array', 'default': [], 'maxItems': 64, 'items': ANY_OBJECT,
                     'title': 'Episodes to add'},
        'state': partial(PERSONA_SCHEMA['properties']['state'], title='State changes'),
        'replace_facts': {'type': 'boolean', 'default': False,
                          'title': 'Replace the fact list instead of appending'}},
       ['persona_id'], {'persona': PERSONA_SCHEMA, 'added': INT}, cancel=False),

    op('export_personas', 'Export characters',
       'Write a self-contained bundle: the sheets, their world, their voice descriptors, and '
       'optionally the reference recordings as a .zip and the scenes played with them. An '
       'imported scene follows its character under a new identifier.',
       {'persona_ids': {'type': 'array', 'default': [], 'maxItems': 100,
                        'items': {'type': 'string', 'maxLength': 80}, 'title': 'Characters'},
        'destination': text('Destination file', '', 1000, 'File'),
        'include_world': {'type': 'boolean', 'default': True},
        'include_voice': {'type': 'boolean', 'default': True},
        'include_audio': {'type': 'boolean', 'default': False,
                          'title': 'Bundle the reference recordings (produces a .zip)'},
        'include_images': {'type': 'boolean', 'default': True,
                           'title': 'Bundle the reference photographs (produces a .zip)'},
        'include_sessions': {'type': 'boolean', 'default': False,
                             'title': 'Bundle the scenes played with them (words, not takes)'}},
       ['persona_ids'],
       {'file': STR, 'personas': {'type': 'array', 'items': STR},
        'worlds': {'type': 'array', 'items': STR}, 'voices': {'type': 'array', 'items': STR},
        'bundledAudio': INT, 'bundledImages': INT},
       cancel=False, permissions=['filesystemExternal']),

    op('list_examples', 'List the example worlds',
       'The example worlds shipped with the Tool — epic fantasy, science fiction, cyberpunk, '
       'gothic horror, post-apocalypse, gentle fantasy — each a bundle of a world and its cast. '
       'Import one with import_personas and the file given here; an import is a copy, and '
       'an existing identifier is never overwritten.',
       {}, [],
       {'examples': {'type': 'array', 'items': {
           'type': 'object', 'properties': {
               'id': STR, 'file': STR, 'world': STR, 'worldId': STR, 'genre': STR, 'tone': STR,
               'summary': STR, 'imported': BOOL,
               'scenes': {'type': 'array', 'items': ANY_OBJECT},
               'characters': {'type': 'array', 'items': ANY_OBJECT}}}},
        'folder': STR}, cancel=False),

    op('import_personas', 'Import characters',
       'Read a bundle, a single sheet or a single world. Existing identifiers are never '
       'overwritten: a clash produces a new identifier unless rename is off.',
       {'file': text('Bundle file', '', 1000, 'File'),
        'rename': {'type': 'boolean', 'default': True,
                   'title': 'Rename on clash instead of failing'}},
       ['file'], {'personas': {'type': 'array', 'items': STR},
                  'worlds': {'type': 'array', 'items': STR},
                  'voices': {'type': 'array', 'items': STR}},
       cancel=False, permissions=['filesystemExternal']),

    # ----------------------------------------------------------------- sessions
    op('list_sessions', 'List sessions', 'Saved conversations, newest first.',
       {'persona_id': ident('Character')}, [],
       {'sessions': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('get_session', 'Read a session', 'A saved conversation with its scene directives.',
       {'persona_id': ident('Character'), 'session_id': text('Session', '', 80)},
       ['persona_id', 'session_id'], {'session': ANY_OBJECT, 'file': STR}, cancel=False),

    op('new_session', 'Start a session', 'Open a fresh conversation for a character.',
       {'persona_id': ident('Character'), 'title': text('Title', '', 200)},
       ['persona_id'], {'session': ANY_OBJECT, 'id': STR}, cancel=False),

    op('remove_session', 'Remove a session',
       'Move a conversation to .trash next to the other sessions of that character.',
       {'persona_id': ident('Character'), 'session_id': text('Session', '', 80)},
       ['persona_id', 'session_id'], {'id': STR, 'trash': STR}, cancel=False),

    op('translate', 'Translate a scene',
       'Translate a stored scene, or a single text, with a language model of your choice. The '
       'translation is written beside each turn — the original is never changed — so a scene '
       'can carry several languages. Delivery marks such as [ton: ...] or [pause: 400ms] are '
       'masked before translation and put back afterwards; any the model loses are reported. '
       'The answer is constrained to one string per turn. Every request carries the context '
       'the words need, never translated itself: the world (genre, tone, setting, the places, '
       'factions and terms mentioned first), who speaks and how, where the scene stands, the '
       'lines just before in their original words, and your own note in context. A text given '
       'together with session_id is translated in the light of that scene, and nothing is '
       'stored. The places, factions and terms of the world read the same in every '
       'translation: each is rendered once per language, recorded in the world '
       '(term_translations; see translation_terms), required in every request, and a line that '
       'drops one is asked again once — termsMissed reports what still does.',
       {'persona_id': ident('Character'),
        'session_id': text('Session', '', 80),
        'text': text('Text to translate instead of a session', '', 24000, 'MultilineString'),
        'world_id': dict(ident('World'), description='The world of a text given without a '
                         'character; a character brings its own.'),
        'context': text('Note for the translator', '', 2000, 'MultilineString'),
        'keep_terms': {'type': 'boolean', 'default': True,
                       'title': 'Record how new terms of the world are rendered',
                       'description': 'The places, factions and glossary terms a text mentions '
                                      'are rendered once per language and recorded in the '
                                      'world, so every later translation says them the same '
                                      'way. Off: rendered for this request only.'},
        'target_language': {'type': 'string', 'enum': LANGUAGES, 'title': 'Translate into'},
        'source_language': {'type': 'string', 'enum': [''] + LANGUAGES, 'default': '',
                            'title': 'Written in',
                            'description': 'Empty uses the character\'s spoken language.'},
        'turns': {'type': 'array', 'default': [], 'maxItems': 2000, 'title': 'Only these turns',
                  'items': {'type': 'integer', 'minimum': 0}},
        'roles': {'type': 'string', 'enum': ['all', 'assistant'], 'default': 'all',
                  'title': 'Which lines',
                  'description': 'all: both sides of the scene. assistant: the character only.'},
        'overwrite': {'type': 'boolean', 'default': False,
                      'title': 'Translate again lines that already have this language'},
        'save': {'type': 'boolean', 'default': True, 'title': 'Store the translation in the session'},
        'llm_model': text('Translation model', '', 60),
        'device': MODEL_OVERRIDES['device'],
        'temperature': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 2, 'default': None,
                        'description': 'Empty uses 0.2: a translation is not a place for invention.'},
        'seed': MODEL_OVERRIDES['seed'],
        'threads': MODEL_OVERRIDES['threads'],
        'keep_loaded': MODEL_OVERRIDES['keep_loaded']},
       ['target_language'],
       {'language': STR, 'source': STR, 'model': STR, 'device': STR,
        'translations': {'type': 'array', 'items': {
            'type': 'object', 'properties': {'turn': {'type': ['integer', 'null']}, 'role': STR,
                                             'original': STR, 'text': STR,
                                             'marksLost': {'type': 'array', 'items': STR}}}},
        'skipped': {'type': 'array', 'items': ANY_OBJECT}, 'text': STR, 'seconds': NUM,
        'saved': BOOL, 'sessionId': STR, 'marksLost': INT, 'file': STR,
        'worldId': STR, 'terms': ANY_OBJECT,
        'termsLearned': {'type': 'array', 'items': STR},
        'termsRejected': {'type': 'array', 'items': STR},
        'termsRetried': INT, 'termsMissed': INT, 'context': BOOL},
       progress=True,
       resources={'ramBytes': 1024 ** 3, 'cpuThreads': 4}),

    op('speak_turn', 'Speak a line of a scene',
       'Speak one of the character\'s stored lines, in the scene\'s own language or in one of its '
       'translations, with the voice the sheet configures for that language. The take is kept '
       'with the session (data/sessions/<character>/audio/) and recorded on the turn.',
       {'persona_id': ident('Character'),
        'session_id': text('Session', '', 80),
        'turn': {'type': 'integer', 'minimum': 0, 'title': 'Line number in the session'},
        'language': SPOKEN_LANGUAGE,
        'keep': {'type': 'boolean', 'default': True, 'title': 'Keep the take with the scene'},
        'model': text('Voice model variant', '', 60),
        'device': {'type': 'string', 'enum': ['cuda', 'cpu'], 'default': 'cuda'},
        'seed': {'type': ['integer', 'null'], 'minimum': -1, 'maximum': 2 ** 31 - 1, 'default': None},
        'delivery': {'type': 'string', 'enum': ['', 'paragraphs', 'segments', 'complete'],
                     'default': ''}},
       ['persona_id', 'session_id', 'turn'],
       {'file': STR, 'workspaceFile': STR, 'mimeType': STR, 'durationSeconds': NUM,
        'sampleRate': INT, 'turn': INT, 'text': STR, 'language': STR, 'voicePlan': VOICE_PLAN,
        'mode': STR, 'model': STR, 'note': STR, 'generationSeconds': NUM},
       progress=True,
       resources={'ramBytes': 8 * 1024 ** 3, 'vramBytes': {'auto': 6 * 1024 ** 3}}),

    op('choose_take', 'Choose the take a line plays',
       'Every take of a line is kept (audio.takes, oldest first); audio itself describes the one '
       'the line plays. This chooses another one — take is its position in audio.takes, from 0.',
       TAKE_TARGET, ['persona_id', 'session_id', 'turn', 'take'], TAKE_OUT, cancel=False),

    op('remove_take', 'Put a take in the trash',
       'Move one take of a line to the trash beside the scene\'s takes '
       '(data/sessions/<character>/audio/<session>/.trash); nothing is deleted. When it was the '
       'take the line plays, the latest take left is played instead.',
       TAKE_TARGET, ['persona_id', 'session_id', 'turn', 'take'],
       {**TAKE_OUT, 'trash': STR, 'left': INT}, cancel=False),

    op('speak_batch', 'Speak a batch of lines',
       'Speak a list of lines — who says what — into a new task folder of data/batches. The '
       'list is sent inline: text holds a script ("Name: line", or "ID | Name: line"), a CSV '
       'or a JSON list (format auto recognises them), or items gives the lines as objects. '
       'Every line gets an id — its own, or its number — and its take is named after it. '
       + BATCH_ABOUT + ' resume continues an earlier task without generating its finished '
       'lines again. To read the list or bring characters from files on disk, use '
       'speak_batch_file.',
       {**BATCH_LIST, 'resume': text('Task to resume', '', 200), **BATCH_OPTIONS},
       [], BATCH_OUT, progress=True,
       resources={'ramBytes': 8 * 1024 ** 3, 'vramBytes': {'auto': 6 * 1024 ** 3}}),

    op('speak_batch_file', 'Speak a batch task from files',
       'speak_batch, with files: the list read from file (a script .txt, a CSV .csv/.tsv or a '
       'JSON list .json; text or items still work), and personas, the characters the task '
       'brings — bundles exported by PersonaRP with their recordings (sheet, world, stable '
       'voices, the per-language ones included). They are copied into the task folder '
       '(personnages/) and never into the library, and are looked up before the library; '
       'use_library false keeps the task to its own characters. ' + BATCH_ABOUT,
       {'file': text('Batch file', '', 1000, 'File'),
        'personas': {'type': 'array', 'maxItems': 64, 'title': 'Characters of the task',
                     'items': text('Character bundle', '', 1000, 'File')},
        'use_library': {'type': 'boolean', 'default': True,
                        'title': 'Also look in the library',
                        'description': 'Off: only the characters and voices the task brought.'},
        **BATCH_LIST, **BATCH_OPTIONS},
       [], BATCH_OUT, progress=True, permissions=['filesystemExternal'],
       resources={'ramBytes': 8 * 1024 ** 3, 'vramBytes': {'auto': 6 * 1024 ** 3}}),

    op('comfyui_nodes_status', 'Find ComfyUI and the PersonaRP nodes',
       'The ComfyUI installations found on this machine (Comfy Desktop), plus comfyui_path when '
       'given, each with whether the PersonaRP nodes are installed and up to date.',
       {'comfyui_path': text('ComfyUI folder', '', 1000)}, [],
       {'comfyui': {'type': 'array', 'items': ANY_OBJECT},
        'nodes': {'type': 'array', 'items': ANY_OBJECT}, 'packDigest': STR, 'toolRoot': STR},
       cancel=False),

    op('install_comfyui_nodes', 'Install the PersonaRP nodes into ComfyUI',
       'Copy the PersonaRP nodes into the custom_nodes folder of a ComfyUI (its folder, its base '
       'directory or custom_nodes itself) with a config.json naming this Tool. The nodes use '
       'the Tool through its local API — they start it on port `port` when it does not answer '
       'and auto_start is on — and never import it. Installing again replaces the copy; '
       'nothing else in ComfyUI is touched. Restart ComfyUI to load them.',
       {'comfyui_path': text('ComfyUI folder', '', 1000),
        'port': {'type': 'integer', 'minimum': 1024, 'maximum': 65535, 'default': 8791,
                 'title': 'Port of the local API'},
        'auto_start': {'type': 'boolean', 'default': True,
                       'title': 'ComfyUI starts the Tool when it does not answer'}},
       ['comfyui_path'],
       {'folder': STR, 'files': INT, 'packDigest': STR, 'toolRoot': STR, 'port': INT,
        'nodes': {'type': 'array', 'items': ANY_OBJECT}},
       cancel=False, permissions=['filesystemExternal']),

    op('list_batches', 'List the voice batches',
       'Every batch folder in data/batches, newest first, with how many of its lines are done.',
       {}, [],
       {'folder': STR, 'batches': {'type': 'array', 'items': {'type': 'object', 'properties': {
           'id': STR, 'name': STR, 'created': STR, 'folder': STR, 'lines': INT, 'done': INT,
           'failed': INT, 'complete': BOOL}}}},
       cancel=False),

    op('translation_terms', 'Read how the terms of a world are translated',
       'The places, factions and glossary terms of a world, each with its rendering in a '
       'language, where it comes from (model or person) and which model rendered it.',
       {'world_id': ident('World'), 'language': {'type': 'string', 'enum': LANGUAGES}},
       ['world_id', 'language'],
       {'worldId': STR, 'language': STR, 'terms': {'type': 'array', 'items': ANY_OBJECT}},
       cancel=False),

    op('set_term_translations', 'Fix how terms of a world are translated',
       'Set the rendering of terms in a language. A rendering set here is never replaced by '
       'the model; an empty text forgets it, so the next translation renders it again.',
       {'world_id': ident('World'), 'language': {'type': 'string', 'enum': LANGUAGES},
        'terms': {'type': 'array', 'maxItems': 500, 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'term': text('Term', '', 120), 'text': text('Rendering', '', 200)},
            'required': ['term']}}},
       ['world_id', 'language', 'terms'],
       {'worldId': STR, 'language': STR, 'changed': {'type': 'array', 'items': STR},
        'revision': INT},
       cancel=False),

    # -------------------------------------------------------------------- scene
    op('scene_prompts', 'Build prompts from a scene directive',
       'Turn a directive into ready-to-use image and video prompts, filling anything the model '
       'left empty from the character sheet and the world. Renders nothing.',
       {'scene': SCENE_SCHEMA, 'persona_id': ident('Character'), 'world_id': ident('World'),
        'targets': {'type': 'array', 'default': [], 'maxItems': 16,
                    'items': {'type': 'string', 'maxLength': 60},
                    'title': 'Extra named forms to keep from the directive'}},
       ['scene'],
       {'image_prompt': STR, 'video_prompt': STR, 'negative_prompt': STR,
        'renderings': ANY_OBJECT, 'summary': STR, 'file': STR}, cancel=False),

    # ------------------------------------------------------- free discussion
    op('assistant_chat', 'Talk to the assistant',
       'One turn of free discussion, with no character and no scene. The thread is written '
       'to disk before the reply comes back, so nothing has to be saved by hand. Several '
       'threads can be open at once.',
       {'thread_id': text('Discussion (empty opens a new one)', '', 80),
        'text': text('Your message', '', 24000, 'MultilineString'),
        'image': text('Reference image read as text first', '', 1000, 'Image'),
        'vision_model': text('Vision model used to read it', '', 60),

        'title': text('Rename the discussion', '', 200),
        'system': text('Standing instruction for this discussion', '', 8000, 'MultilineString'),
        'context_budget': {'type': ['integer', 'null'], 'minimum': 1024, 'maximum': 60000,
                           'default': None, 'title': 'Characters of history kept'},
        **MODEL_OVERRIDES},
       ['text'],
       {'text': STR, 'threadId': STR, 'title': STR,
        'turns': {'type': 'array', 'items': ANY_OBJECT}, 'seconds': NUM, 'reused': BOOL,
        'truncated': BOOL, 'picture': ANY_OBJECT, 'context': ANY_OBJECT, 'file': STR,
        'mimeType': STR},
       progress=True,
       resources={'ramBytes': 1024 ** 3, 'cpuThreads': 8}),

    op('list_assistant_threads', 'List discussions', 'Saved discussions, newest first.',
       {}, [], {'threads': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('new_assistant_thread', 'Open a discussion', 'Start an empty discussion thread.',
       {'title': text('Title', '', 200),
        'system': text('Standing instruction', '', 8000, 'MultilineString')},
       [], {'thread': ANY_OBJECT, 'id': STR}, cancel=False),

    op('get_assistant_thread', 'Read a discussion', 'A discussion with all of its turns.',
       {'thread_id': text('Discussion', '', 80)}, ['thread_id'],
       {'thread': ANY_OBJECT, 'file': STR}, cancel=False),

    op('save_assistant_thread', 'Save a discussion',
       'Keep the title, the standing instruction, the unsent draft and the model settings '
       'of a discussion without sending anything.',
       {'thread_id': text('Discussion', '', 80), 'title': text('Title', '', 200),
        'system': text('Standing instruction', '', 8000, 'MultilineString'),
        'draft': text('Unsent draft', '', 24000, 'MultilineString'),
        'llm_model': text('Model', '', 60),
        'device': {'type': 'string', 'enum': ['', 'cpu', 'cuda'], 'default': ''},
        'temperature': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 2, 'default': None},
        'response_length': {'type': ['integer', 'null'], 'minimum': 16, 'maximum': 4096,
                            'default': None}},
       ['thread_id'], {'thread': ANY_OBJECT}, cancel=False),

    op('remove_assistant_thread', 'Remove a discussion',
       'Move a discussion to data/assistant/.trash. Nothing is deleted.',
       {'thread_id': text('Discussion', '', 80)}, ['thread_id'],
       {'id': STR, 'trash': STR}, cancel=False),

    # -------------------------------------------------------------- photographs
    op('list_images', 'List the photographs',
       'Every reference photograph held by the library, with the character it belongs to and '
       'whether the file is still there.',
       {'persona_id': ident('Only this character')}, [],
       {'images': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('add_persona_image', 'Add a photograph to a character',
       'Copy a reference photograph beside the sheet. It is kept with the character, travels '
       'with an export, and can be read by a vision model to fill the appearance. The roleplay '
       'model never sees it.',
       {'persona_id': ident('Character'),
        'image': text('Image (PNG, JPEG, WebP, BMP)', '', 1000, 'Image'),
        'role': {'type': 'string', 'default': 'reference', 'title': 'What it shows',
                 'enum': ['portrait', 'full_body', 'outfit', 'detail', 'expression', 'setting',
                          'reference']},
        'caption': text('Caption', '', 600)},
       ['persona_id', 'image'],
       {'persona': PERSONA_SCHEMA, 'references': {'type': 'array', 'items': ANY_OBJECT},
        'file': STR}, cancel=False, permissions=['filesystemExternal']),

    op('remove_persona_image', 'Remove a photograph',
       'Move a photograph to the character\'s image trash. Nothing is deleted.',
       {'persona_id': ident('Character'), 'file': text('File', '', 1000)},
       ['persona_id', 'file'],
       {'persona': PERSONA_SCHEMA, 'references': {'type': 'array', 'items': ANY_OBJECT},
        'trash': STR}, cancel=False),

    op('verify_persona_images', 'Verify the photographs',
       'Check that every photograph of a sheet is still present and unchanged.',
       {'persona_id': ident('Character')}, ['persona_id'],
       {'references': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('describe_image', 'Describe a character from a photograph',
       'Read a reference photograph with a vision model and return the appearance branch: '
       'build, face, hair, eyes, skin, outfit, marks, accessories, and the visual tags that '
       'every later image prompt repeats word for word. Two passes: the model first describes '
       'the picture in free prose (returned as observation, in English), then writes the '
       'fields from that observation in the language asked, as phrases rather than single '
       'words. The result is a proposal — apply it with apply_proposal.',
       {'persona_id': ident('Character'), 'persona': optional(PERSONA_SCHEMA),
        'file': text('Photograph on the sheet (empty uses the first one)', '', 1000),
        'image': text('Any image instead, read without touching a sheet', '', 1000, 'Image'),
        'use_existing': {'type': 'boolean', 'default': True,
                         'title': 'Show the model what the sheet already says',
                         'description': 'It then corrects rather than starting from nothing.'},
        'language': text('Language of the description', '', 60),
        'llm_model': text('Vision model', '', 60),
        'device': {'type': 'string', 'enum': ['', 'cpu', 'cuda'], 'default': ''},
        'keep_loaded': {'type': 'boolean', 'default': False}},
       [],
       {'proposal': ANY_OBJECT, 'text': STR, 'target': STR, 'kind': STR, 'model': STR,
        'source': STR, 'seconds': NUM, 'sentWidth': INT, 'sentHeight': INT, 'file': STR,
        'observation': STR},
       progress=True,
       resources={'ramBytes': 1024 ** 3, 'cpuThreads': 4}),

    # -------------------------------------------------------------------- voice
    op('speak', 'Speak a text',
       'Render speech with a character\'s voice, or with an explicit voice. Delivery marks '
       'written in the text — [ton: …], [pause: 400ms], [emotion: …] — steer the take and are '
       'never pronounced.',
       {'text': text('Text to speak', '', 24000, 'MultilineString'),
        'persona_id': ident('Character whose voice to use'),
        'voice_id': text('Stable voice', '', 80),
        'voice': partial(VOICE_SCHEMA, title='Voice settings override',
                         description='Only the fields given here replace the character\'s own.'),
        'language': SPOKEN_LANGUAGE,
        'model': text('Voice model variant', '', 60),
        'device': {'type': 'string', 'enum': ['cuda', 'cpu'], 'default': 'cuda'},
        'seed': {'type': ['integer', 'null'], 'minimum': -1, 'maximum': 2 ** 31 - 1, 'default': None},
        'delivery': {'type': 'string', 'enum': ['', 'paragraphs', 'segments', 'complete'],
                     'default': ''}},
       ['text'],
       {'file': STR, 'mimeType': STR, 'durationSeconds': NUM, 'sampleRate': INT,
        'segments': {'type': 'array', 'items': ANY_OBJECT}, 'chunks': {'type': 'array', 'items': STR},
        'mode': STR, 'model': STR, 'note': STR, 'generationSeconds': NUM, 'language': STR,
        'voicePlan': VOICE_PLAN},
       progress=True,
       resources={'ramBytes': 8 * 1024 ** 3, 'vramBytes': {'auto': 6 * 1024 ** 3}}),

    op('capture_voice_take', 'Capture a voice take',
       'Produce the reference recording a stable voice is built from: roughly 12 to 24 seconds '
       'of speech, from a written voice description, from a preset speaker, or from your own '
       'text. Returns the take and its transcript so it can be registered straight away.',
       {'persona_id': ident('Character'),
        'description': text('Voice to invent', '', 800, 'MultilineString'),
        'speaker': text('Preset speaker', '', 60),
        'text': text('What the take says', '', 4000, 'MultilineString'),
        'model': text('Voice model variant', '', 60),
        'language': {'type': 'string', 'enum': ['', 'Auto'] + LANGUAGES, 'default': '',
                     'title': 'Language of the take',
                     'description': 'Empty uses the character\'s spoken language. With no text '
                                    'given, the default take is written in this language.'},
        'device': {'type': 'string', 'enum': ['cuda', 'cpu'], 'default': 'cuda'},
        'seed': {'type': ['integer', 'null'], 'minimum': -1, 'maximum': 2 ** 31 - 1, 'default': None},
        'transcribe': {'type': 'boolean', 'default': False,
                       'title': 'Transcribe the take instead of trusting the written text',
                       'description': 'Slower, but it records what the model really said.'}},
       [], {'file': STR, 'workspaceFile': STR, 'transcript': STR, 'durationSeconds': NUM,
            'inRange': BOOL, 'advice': STR, 'mode': STR, 'model': STR, 'language': STR,
            'mimeType': STR},
       progress=True,
       resources={'ramBytes': 8 * 1024 ** 3, 'vramBytes': {'auto': 6 * 1024 ** 3}}),

    op('create_stable_voice', 'Create a stable voice',
       'Register a recording as a reusable voice. Every later line of that character is cloned '
       'from this take, so the voice stops drifting between replies and between sessions. The '
       'exact words of the take are required; they can be transcribed here.',
       {'name': text('Voice name', '', 120),
        'audio': text('Recording', '', 1000, 'File'),
        'transcript': text('Exact words of the recording', '', 4000, 'MultilineString'),
        'persona_id': ident('Character this voice belongs to'),
        'attach': {'type': 'boolean', 'default': True,
                   'title': 'Attach it to that character straight away'},
        'for_language': {'type': 'string', 'enum': [''] + LANGUAGES, 'default': '',
                         'title': 'Attach it for one language only',
                         'description': 'Empty makes it the character\'s main voice. A language '
                                        'makes it the voice of that language only — the main '
                                        'voice is kept.'},
        'model': text('Voice model variant', '1.7B-Base', 60),
        'language': text('Language', 'Auto', 40),
        'description': text('Notes on the voice', '', 2000),
        'source': {'type': 'string', 'enum': ['generated', 'imported', 'designed'],
                   'default': 'generated'},
        'transcribe': {'type': 'boolean', 'default': False,
                       'title': 'Transcribe the recording to obtain the exact words'},
        'device': {'type': 'string', 'enum': ['cuda', 'cpu'], 'default': 'cuda'}},
       ['name', 'audio'],
       {'voice': STABLE_VOICE_SCHEMA, 'id': STR, 'attached': BOOL, 'forLanguage': STR,
        'warning': STR},
       progress=True, permissions=['filesystemExternal']),

    op('list_voices', 'List stable voices', 'Voices in the library, with their reference take.',
       {'persona_id': ident('Only this character')}, [],
       {'voices': {'type': 'array', 'items': ANY_OBJECT}}, cancel=False),

    op('verify_voice', 'Verify a stable voice',
       'Check that the reference recording is still present and unchanged. A changed reference '
       'means the voice would no longer sound the same.',
       {'voice_id': text('Voice', '', 80)}, ['voice_id'],
       {'id': STR, 'ok': BOOL, 'reason': STR}, cancel=False),

    op('remove_voice', 'Remove a stable voice',
       'Move a voice and its recording to data/voices/.trash. Nothing is deleted.',
       {'voice_id': text('Voice', '', 80)}, ['voice_id'], {'id': STR, 'trash': STR}, cancel=False),

    op('transcribe', 'Transcribe a recording',
       'Speech to text with Whisper, for a reference take or for dictating a message.',
       {'audio': text('Recording', '', 1000, 'File'),
        'language': text('Language code (empty detects it)', '', 8),
        'device': {'type': 'string', 'enum': ['cuda', 'cpu'], 'default': 'cuda'},
        'timestamps': {'type': 'boolean', 'default': True}},
       ['audio'],
       {'text': STR, 'segments': {'type': 'array', 'items': ANY_OBJECT}, 'durationSeconds': NUM,
        'seconds': NUM, 'file': STR},
       progress=True, permissions=['filesystemExternal'],
       resources={'ramBytes': 6 * 1024 ** 3, 'vramBytes': {'auto': 4 * 1024 ** 3}}),

    op('list_voice_models', 'List voice models',
       'Speech models and their installation state, size, licence and source.',
       {'verify': {'type': 'boolean', 'default': False}}, [],
       {'models': {'type': 'array', 'items': ANY_OBJECT}, 'engine': ANY_OBJECT,
        'workers': ANY_OBJECT}, progress=True),

    op('install_voice_model', 'Install a voice model',
       'Download, resume or repair a speech model. The licence must be accepted personally.',
       {'model': text('Model', '', 80),
        'accept_license': {'type': 'boolean', 'default': False,
                           'title': 'I personally accept this model licence'}},
       ['model'], {'model': STR, 'installed': BOOL, 'sizeBytes': INT},
       progress=True, permissions=['network']),

    op('install_voice_engine', 'Install the voice engine',
       'Create or repair the private speech environment (PyTorch, Qwen3-TTS, Whisper) at its '
       'final path, then import-check it. Nothing is recorded as installed before that passes.',
       {'cpu_only': {'type': 'boolean', 'default': False,
                     'title': 'Accept a CPU-only engine (much slower)'}},
       [], {'installed': BOOL, 'log': STR, 'report': ANY_OBJECT},
       progress=True, permissions=['network'],
       resources={'diskBytes': 9 * 1024 ** 3}),

    op('release_voice', 'Release the voice workers',
       'Stop the speech processes and free their RAM and VRAM.',
       {}, [], {'released': BOOL}, cancel=False),

    # ------------------------------------------------------------------- models
    op('list_models', 'List conversation models',
       'Catalogue with installation state, size, bytes present, licence and source.',
       {'verify': {'type': 'boolean', 'default': False,
                   'title': 'Re-check the SHA-256 of installed files'}},
       [], {'models': {'type': 'array', 'items': ANY_OBJECT}, 'engine': ANY_OBJECT},
       progress=True),

    op('install_llm', 'Install a conversation model',
       'Download, resume or repair the weights of one catalogue model. The licence must be '
       'accepted personally first.',
       {'model': text('Model', '', 60),
        'accept_license': {'type': 'boolean', 'default': False,
                           'title': 'I personally accept this model licence'}},
       ['model'], {'model': STR, 'installed': BOOL, 'sizeBytes': INT},
       progress=True, permissions=['network']),

    op('install_cuda', 'Install the NVIDIA CUDA engine',
       'Download and verify the Windows x64 CUDA build of llama.cpp, then test it against the '
       'installed driver before recording it.',
       {}, [], {'installed': BOOL, 'version': STR, 'devices': STR},
       progress=True, permissions=['network']),

    op('unload_model', 'Unload the resident model',
       'Stop the conversation server and release its RAM and VRAM reservation.',
       {}, [], {'loaded': BOOL}, cancel=False),

    op('diagnose_backend', 'Diagnose',
       'Models, engines, devices, library counts and the storage layout actually in use.',
       {'verify': {'type': 'boolean', 'default': False}}, [],
       {'models': {'type': 'array', 'items': ANY_OBJECT}, 'engine': ANY_OBJECT,
        'library': ANY_OBJECT, 'platform': STR, 'resident': ANY_OBJECT, 'paths': ANY_OBJECT,
        'file': STR}, progress=True),

    op('update', 'Update',
       'Check, stage, activate or roll back the application or the engine. Weights follow their '
       'own catalogue. data/ is never part of a replacement.',
       {'kind': {'type': 'string', 'enum': ['app', 'engine'], 'default': 'engine'},
        'action': {'type': 'string', 'enum': ['check', 'download', 'activate', 'rollback'],
                   'default': 'check'},
        'repository': dict(text('GitHub repository (owner/name)', '', 200),
                           description='Empty uses the repository this application ships with '
                                       '(release.json).')},
       [], {'message': STR, 'version': STR, 'updateAvailable': BOOL},
       progress=True, permissions=['network']),
]


MANIFEST = {
    'schemaVersion': 1,
    'protocolVersion': '1.0',
    'id': 'cy.tool.personarp',
    'name': 'CyTools_PersonaRP',
    'version': VERSION,
    'description': ('Persistent characters: complete sheets, shared world lore, relationships, '
                    'evolving dialogue, delivery annotations, and machine-readable scene '
                    'descriptions for image and video tools. Runs locally.'),
    'vendor': 'Cyberalien',
    'author': 'Cyberalien',
    'license': 'GPL-3.0-only',
    'homepage': 'https://github.com/MrMybal/CyTools_PersonaRP',
    'executable': 'runtime/python/Scripts/python.exe app/tool.py',
    'standaloneExecutable': 'CyTools_PersonaRP.exe',
    'categories': ['generation', 'utility'],
    'tags': ['roleplay', 'characters', 'lore', 'dialogue', 'local-llm'],
    'capabilities': ['jobs', 'cancellation', 'progress'],
    # `tested` stays empty until a run really happened on this machine; entries are added
    # from data/reports, never from an assumption.
    'platforms': [
        {'os': 'Windows', 'architecture': 'x64', 'status': 'Experimental',
         'computeBackends': ['CPU', 'CUDA'], 'tested': TESTED_WINDOWS},
        {'os': 'Linux', 'architecture': 'x64', 'status': 'Experimental',
         'computeBackends': ['CPU'], 'notes': 'Launcher provided, never executed.',
         'tested': []},
    ],
    'interfaces': ['Native', 'CLI', 'JSONL', 'HTTP', 'MCP', 'ImGui'],
    'runtimeRequirements': [],
    # Concurrent: a list, a sheet or a session is answered while a generation runs. The jobs
    # that use the GPU or stop an engine take turns on the execution lock (personarp/locks.py).
    'concurrency': {'policy': 'Concurrent', 'maxWorkers': 16},
    'backends': [{'id': 'llamacpp', 'name': 'llama.cpp', 'kind': 'Local',
                  'description': 'Local GGUF inference on CPU or NVIDIA CUDA.'}],
    'operations': OPERATIONS,
    'distributionStatus': 'In development: see VALIDATION.md for what has actually been executed.',
}


def build():
    for operation in MANIFEST['operations']:
        operation.setdefault('supportedBackends', [])
    path = APP / 'CyTool.json'
    path.write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding='utf-8')
    from cytools_core import load_manifest
    load_manifest(path)
    return path


if __name__ == '__main__':
    print(build())
