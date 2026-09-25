"""JSON contracts for personas, worlds, relationships, voices and scene directives.

These schemas are the portable format. A persona exported from this Tool is one JSON
document validated here; nothing about it depends on the GUI or on a particular model.

Text fields are bounded so a sheet can never silently blow the model's context: the
prompt builder still applies its own budget on top (see prompting.py).
"""
import copy

from cytools_core.schema import validate_parameters

FORMAT_PERSONA = 'cytools-personarp-persona'
FORMAT_WORLD = 'cytools-personarp-world'
FORMAT_BUNDLE = 'cytools-personarp-bundle'
SCHEMA_VERSION = 1


def _text(title, limit=4000, default='', description=''):
    spec = {'type': 'string', 'maxLength': limit, 'default': default, 'title': title}
    if description:
        spec['description'] = description
    return spec


def _lines(title, limit=400, description=''):
    """A list of short entries — traits, tags, goals. Easier to reuse than free prose."""
    spec = {'type': 'array', 'default': [], 'title': title, 'maxItems': 64,
            'items': {'type': 'string', 'maxLength': limit}}
    if description:
        spec['description'] = description
    return spec


def _object(title, properties, description=''):
    spec = {'type': 'object', 'title': title, 'default': {}, 'additionalProperties': False,
            'properties': properties}
    if description:
        spec['description'] = description
    return spec


# --------------------------------------------------------------------------- voice

# The languages Qwen3-TTS speaks. "Auto" lets the model guess from the text.
LANGUAGES = ['French', 'English', 'Spanish', 'German', 'Italian', 'Portuguese', 'Russian',
             'Chinese', 'Japanese', 'Korean']

# How a character sounds in a language other than its own. Two wishes are both legitimate
# and they are opposite: keep the very same voice, accent included, or switch to a voice
# that really belongs to that language. Neither is a default the Tool may pick for you.
LANGUAGE_VOICE_SCHEMA = _object('Voice in one language', {
    'language': {'type': 'string', 'enum': LANGUAGES, 'default': 'English',
                 'title': 'Language'},
    'source': {'type': 'string', 'enum': ['same', 'voice', 'design', 'preset'],
               'default': 'same', 'title': 'Voice used',
               'description': 'same: the character\'s own voice speaking this language. '
                              'voice: another stable voice, typically captured from a take in '
                              'this language. design: a voice invented from a description. '
                              'preset: one of the preset speakers.'},
    'accent': {'type': 'string', 'enum': ['keep', 'native'], 'default': 'keep',
               'title': 'Accent',
               'description': 'With the same voice. keep: the character keeps the accent of its '
                              'own take. native: only the timbre is kept and the words are '
                              'pronounced the way the model pronounces this language.'},
    'voice_id': _text('Stable voice for this language', 80),
    'description': _text('Voice to invent for this language', 800),
    'speaker': _text('Preset speaker', 60, 'Ryan'),
    'instruction': _text('Direction for this language', 1000,
                         description='Read by invented and preset voices. A cloned voice '
                                     'reproduces its take and takes no written direction.'),
    'seed': {'type': 'integer', 'minimum': -1, 'maximum': 2 ** 31 - 1, 'default': -1,
             'title': 'Seed', 'description': '-1 keeps the seed of the main voice.'},
}, 'One entry per language the character should speak differently.')

VOICE_SCHEMA = _object('Voice', {
    'enabled': {'type': 'boolean', 'default': False, 'title': 'Speak replies'},
    'voice_id': _text('Stable voice', 80, description='Identifier of a stable voice in data/voices.'),
    'backend': {'type': 'string', 'enum': ['qwen3tts', 'piper', 'none'], 'default': 'qwen3tts'},
    'model': _text('Voice model', 60, '1.7B-CustomVoice'),
    'speaker': _text('Preset speaker', 60, description='Used when no stable voice is attached.'),
    'language': {'type': 'string', 'default': 'Auto', 'title': 'Spoken language',
                 'enum': ['Auto'] + LANGUAGES,
                 'description': 'The language the character\'s lines are written in. It wins '
                                'over the language recorded on the stable voice.'},
    'languages': {'type': 'array', 'default': [], 'maxItems': len(LANGUAGES),
                  'title': 'Other languages', 'items': LANGUAGE_VOICE_SCHEMA,
                  'description': 'How the character sounds when a translated line is spoken. '
                                 'A language with no entry uses the same voice, accent kept.'},
    'speed': {'type': 'number', 'minimum': 0.25, 'maximum': 4.0, 'default': 1.0},
    'pitch': {'type': 'number', 'minimum': -12.0, 'maximum': 12.0, 'default': 0.0},
    'instruction': _text('Standing voice direction', 2000,
                         description='How this character always sounds, independent of the line.'),
    'description': _text('Voice to invent', 800,
                         description='A written portrait of the voice — age, grain, pace, accent. '
                                     'With no stable voice attached, this is what VoiceDesign '
                                     'builds from, which is also the easiest way to produce the '
                                     'first take a stable voice is then captured from.'),
    'use_persona_style': {'type': 'boolean', 'default': True,
                          'title': 'Derive delivery from the persona and the scene'},
    'annotations': {'type': 'boolean', 'default': True,
                    'title': 'Let the model write [tone:] and [pause:] marks'},
    'speak_narration': {'type': 'boolean', 'default': False,
                        'title': 'Also speak *stage directions*',
                        'description': 'Off by default: the voice says the dialogue, not the '
                                       'narration around it. The scene directive is never spoken.'},
    'delivery': {'type': 'string', 'enum': ['paragraphs', 'complete'], 'default': 'paragraphs',
                 'description': 'Play paragraph by paragraph, or wait for the whole take.'},
}, 'How this character is heard.')

# A stable voice: the point of capturing 12-24 s once is that every later line matches it.
STABLE_VOICE_SCHEMA = _object('Stable voice', {
    'id': _text('Identifier', 80),
    'name': _text('Name', 120),
    'persona_id': _text('Owning persona', 80),
    'backend': {'type': 'string', 'enum': ['qwen3tts', 'piper'], 'default': 'qwen3tts'},
    'model': _text('Voice model', 60, '1.7B-Base',
                   description='Cloning runs on a Base variant; CustomVoice and VoiceDesign '
                               'cannot reproduce a reference recording.'),
    'reference_audio': _text('Reference recording', 1000),
    'reference_text': _text('Exact transcript of the reference', 4000),
    'reference_seconds': {'type': 'number', 'minimum': 0.0, 'maximum': 600.0, 'default': 0.0},
    'reference_sha256': _text('Reference fingerprint', 64),
    'source': {'type': 'string', 'default': 'generated',
               'enum': ['generated', 'imported', 'designed'],
               'description': 'generated: built from a take produced here. '
                              'imported: built from a recording you supplied. '
                              'designed: built from a written voice description.'},
    'description': _text('Voice description', 2000),
    'language': _text('Language', 40, 'Auto'),
    'seed': {'type': 'integer', 'minimum': -1, 'maximum': 2 ** 31 - 1, 'default': -1},
    'locked': {'type': 'boolean', 'default': False,
               'title': 'Locked', 'description': 'A locked voice refuses silent parameter drift.'},
    'created': _text('Created', 40),
    'notes': _text('Notes', 2000),
}, 'A reusable voice built from a short reference take.')


# ----------------------------------------------------------------------- appearance

APPEARANCE_SCHEMA = _object('Appearance', {
    'summary': _text('In one look', 1200),
    'build': _text('Build and height', 300),
    'face': _text('Face', 600),
    'hair': _text('Hair', 300),
    'eyes': _text('Eyes', 300),
    'skin': _text('Skin', 300),
    'outfit': _text('Usual outfit', 800),
    'marks': _text('Scars, tattoos, distinguishing marks', 600),
    'accessories': _text('Carried items and accessories', 600),
    'age_reading': _text('Apparent age', 120),
    'visual_tags': _lines('Visual tags', 80,
                          'Short tags reused verbatim in image prompts, for consistency.'),
    'negative_tags': _lines('Never depict', 80),
    'style_reference': _text('Rendering style', 400,
                             description='Art direction: medium, palette, lens, grain.'),
}, 'Everything a renderer needs to draw this character the same way twice.')

# Photographs attached to a sheet. They are reference material and input for the vision
# model that fills the appearance branch; the roleplay model never sees them.
REFERENCE_SCHEMA = _object('Reference photograph', {
    'file': _text('File', 1000),
    'role': {'type': 'string', 'default': 'reference', 'title': 'What it shows',
             'enum': ['portrait', 'full_body', 'outfit', 'detail', 'expression', 'setting',
                      'reference']},
    'caption': _text('Caption', 600),
    'sha256': _text('Fingerprint', 64),
    'width': {'type': 'integer', 'minimum': 0, 'default': 0},
    'height': {'type': 'integer', 'minimum': 0, 'default': 0},
    'bytes': {'type': 'integer', 'minimum': 0, 'default': 0},
    'mimeType': _text('Type', 60),
    'added': _text('Added', 40),
})


# ---------------------------------------------------------------------- personality

PERSONALITY_SCHEMA = _object('Personality', {
    'summary': _text('In one sentence', 800),
    'traits': _lines('Traits', 80),
    'values': _lines('Values', 160),
    'desires': _lines('Wants', 200),
    'fears': _lines('Fears', 200),
    'flaws': _lines('Flaws', 200),
    'quirks': _lines('Quirks and habits', 200),
    'humour': _text('Sense of humour', 400),
    'temperament': _text('Baseline temperament', 400),
    'moral_compass': _text('Moral compass', 600),
}, 'Who the character is, independent of any scene.')

SPEECH_SCHEMA = _object('Speech', {
    'style': _text('Speaking style', 1200),
    'register': _text('Register', 300, description='Formal, street, archaic, clinical...'),
    'vocabulary': _text('Vocabulary and imagery', 600),
    'accent': _text('Accent', 300),
    'verbal_tics': _lines('Verbal tics', 120),
    'catchphrases': _lines('Catchphrases', 200),
    'languages': _lines('Languages spoken', 60),
    'narration_style': _text('Narration style', 600,
                             default='Short actions between asterisks, then dialogue.'),
    'example_dialogues': _text('Example dialogues', 6000),
}, 'How the character sounds on the page.')

BACKGROUND_SCHEMA = _object('Background', {
    'origin': _text('Origin', 1200),
    'story': _text('Life story', 8000),
    'occupation': _text('Occupation or role', 400),
    'skills': _lines('Skills', 200),
    'possessions': _lines('Notable possessions', 200),
    'secrets': _text('Secrets', 2000, description='Known to you, not necessarily revealed in play.'),
    'factions': _lines('Factions and affiliations', 160),
}, 'Where the character comes from.')

# The evolving part. Everything above is the character; this is the character right now.
STATE_SCHEMA = _object('Current state', {
    'scenario': _text('Scene in progress', 4000),
    'location': _text('Location', 400),
    'time': _text('Time and date in fiction', 300),
    'mood': _text('Mood', 300),
    'energy': _text('Physical condition', 300),
    'outfit_now': _text('Currently wearing', 600),
    'goals': _lines('Immediate goals', 300),
    'tensions': _lines('Open tensions', 300),
    'updated': _text('Last updated', 40),
}, 'What changes as the story advances.')

MEMORY_SCHEMA = _object('Memory', {
    'facts': _lines('Persistent facts', 500,
                    'Always injected. Kept explicit: nothing is harvested from conversations '
                    'without you applying it.'),
    'episodes': {'type': 'array', 'default': [], 'title': 'Remembered episodes', 'maxItems': 500,
                 'items': _object('Episode', {
                     'when': _text('When', 80),
                     'summary': _text('What happened', 1200),
                     'weight': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0, 'default': 0.5},
                     'session_id': _text('Session', 80),
                     'pinned': {'type': 'boolean', 'default': False},
                 })},
}, 'What the character carries between sessions.')

MEDIA_SCHEMA = _object('Visual direction', {
    'enabled': {'type': 'boolean', 'default': False,
                'title': 'Ask for a scene description with each reply'},
    'mode': {'type': 'string', 'enum': ['director', 'inline'], 'default': 'director',
             'title': 'How the description is produced',
             'description': 'director: a second, constrained pass reads the reply and emits the '
                            'directive, so the JSON is always valid and never leaks into the '
                            'dialogue. inline: the same model is asked for both at once — one '
                            'generation instead of two, but small models often skip it.'},
    'detail': {'type': 'string', 'enum': ['minimal', 'standard', 'full'], 'default': 'standard'},
    'director_model': _text('Model used for the description', 60,
                            description='Empty reuses the conversation model. A larger, more '
                                        'instruction-following model usually writes better shot '
                                        'descriptions than a small roleplay model, at the cost '
                                        'of loading a second set of weights.'),
    'default_shot': _text('Default framing', 200, 'medium shot, eye level'),
    'motion_style': _text('Movement style', 600),
    'camera_notes': _text('Camera notes', 600),
    'duration_seconds': {'type': 'number', 'minimum': 1.0, 'maximum': 60.0, 'default': 5.0},
    'aspect_ratio': _text('Aspect ratio', 20, '16:9'),
    'extra_targets': _lines('Extra rendering targets', 60,
                            'Named forms the model should also fill in "renderings", for a '
                            'downstream tool that expects its own shape.'),
}, 'Movement, image and video descriptions — this Tool describes, it does not render.')

GENERATION_SCHEMA = _object('Generation', {
    'llm_model': _text('Conversation model', 60, 'nymphaea'),
    'device': {'type': 'string', 'enum': ['cpu', 'cuda'], 'default': 'cpu'},
    'system_prompt': _text('System prompt', 8000,
                           'Play the character described in this sheet. Stay coherent with the world.'),
    'behaviour_rules': _text('Behaviour rules', 4000),
    'language': _text('Reply language', 60, 'Francais'),
    'temperature': {'type': 'number', 'minimum': 0.0, 'maximum': 2.0, 'default': 0.85},
    'top_p': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0, 'default': 0.95},
    'repeat_penalty': {'type': 'number', 'minimum': 0.5, 'maximum': 2.0, 'default': 1.08},
    'response_length': {'type': 'integer', 'minimum': 16, 'maximum': 4096, 'default': 400},
    'seed': {'type': 'integer', 'minimum': -1, 'maximum': 2 ** 31 - 1, 'default': -1},
    'threads': {'type': 'integer', 'minimum': 1, 'maximum': 64, 'default': 4},
    'stay_in_character': {'type': 'boolean', 'default': True},
    'allow_narration': {'type': 'boolean', 'default': True},
    'context_budget': {'type': 'integer', 'minimum': 1024, 'maximum': 131072, 'default': 8192,
                       'description': 'Characters of assembled prompt kept for the sheet, world '
                                      'and history together.'},
}, 'Model settings carried by the character, so a persona reads the same way every time.')

RELATION_SCHEMA = _object('Relationship', {
    'persona_id': _text('Other character', 80),
    'name': _text('Name as known', 120,
                  description='Kept so an exported sheet still reads when the other persona is absent.'),
    'type': _text('Kind of bond', 80, description='sibling, rival, mentor, lover, employer...'),
    'label': _text('How this character names them', 120),
    'sentiment': {'type': 'number', 'minimum': -1.0, 'maximum': 1.0, 'default': 0.0,
                  'description': '-1 hostile, 0 neutral, 1 devoted.'},
    'trust': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0, 'default': 0.5},
    'history': _text('Shared history', 3000),
    'tension': _text('Current tension', 1000),
    'secret': _text('Kept from them', 1000),
    'known': {'type': 'boolean', 'default': True,
              'title': 'They have met', 'description': 'False for a one-sided or rumoured bond.'},
})

PERSONA_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'default': {},
    'properties': {
        'format': {'type': 'string', 'default': FORMAT_PERSONA},
        'schemaVersion': {'type': 'integer', 'default': SCHEMA_VERSION},
        'id': _text('Identifier', 80),
        'name': _text('Character name', 120, 'New character'),
        'aliases': _lines('Other names', 120),
        'pronouns': _text('Pronouns', 60),
        'age': _text('Age', 80),
        'species': _text('Species or kind', 120),
        'world_id': _text('World', 80, description='The shared lore this character belongs to.'),
        'summary': _text('Pitch', 1200, description='Two lines that place the character.'),
        'tags': _lines('Tags', 60),
        'enabled': {'type': 'boolean', 'default': True, 'title': 'Roleplay this sheet'},
        'appearance': APPEARANCE_SCHEMA,
        'references': {'type': 'array', 'default': [], 'maxItems': 32,
                       'title': 'Reference photographs', 'items': REFERENCE_SCHEMA},
        'personality': PERSONALITY_SCHEMA,
        'speech': SPEECH_SCHEMA,
        'background': BACKGROUND_SCHEMA,
        'state': STATE_SCHEMA,
        'memory': MEMORY_SCHEMA,
        'relationships': {'type': 'array', 'default': [], 'maxItems': 200,
                          'title': 'Relationships', 'items': RELATION_SCHEMA},
        'voice': VOICE_SCHEMA,
        'media': MEDIA_SCHEMA,
        'generation': GENERATION_SCHEMA,
        'created': _text('Created', 40),
        'modified': _text('Modified', 40),
        'revision': {'type': 'integer', 'minimum': 0, 'default': 0,
                     'description': 'Incremented on every save; the character evolves in place '
                                    'and past revisions are kept next to the sheet.'},
        'notes': _text('Private notes', 4000),
    },
}

WORLD_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'default': {},
    'properties': {
        'format': {'type': 'string', 'default': FORMAT_WORLD},
        'schemaVersion': {'type': 'integer', 'default': SCHEMA_VERSION},
        'id': _text('Identifier', 80),
        'name': _text('World name', 120, 'New world'),
        'summary': _text('Pitch', 2000),
        'genre': _text('Genre', 200),
        'tone': _text('Tone', 400),
        'era': _text('Era', 200),
        'setting': _text('Setting', 8000),
        'locations': {'type': 'array', 'default': [], 'maxItems': 200, 'title': 'Locations',
                      'items': _object('Location', {
                          'name': _text('Name', 120),
                          'description': _text('Description', 2000),
                          'tags': _lines('Tags', 60),
                      })},
        'factions': {'type': 'array', 'default': [], 'maxItems': 200, 'title': 'Factions',
                     'items': _object('Faction', {
                         'name': _text('Name', 120),
                         'description': _text('Description', 2000),
                         'stance': _text('Stance towards outsiders', 400),
                     })},
        'rules': {'type': 'array', 'default': [], 'maxItems': 100, 'title': 'Laws of this world',
                  'items': _object('Rule', {
                      'name': _text('Name', 120),
                      'description': _text('How it works', 2000),
                  })},
        'history': {'type': 'array', 'default': [], 'maxItems': 200, 'title': 'Timeline',
                    'items': _object('Event', {
                        'when': _text('When', 120),
                        'what': _text('What happened', 2000),
                    })},
        'glossary': {'type': 'array', 'default': [], 'maxItems': 300, 'title': 'Glossary',
                     'items': _object('Term', {
                         'term': _text('Term', 120),
                         'meaning': _text('Meaning', 1000),
                     })},
        'canon': _text('Canon notes', 6000, description='What must stay true in every scene.'),
        'forbidden': _text('Out of bounds', 2000,
                           description='What never happens here, whatever a scene suggests.'),
        'narration_style': _text('House narration style', 1000),
        'language': _text('Default language', 60, 'Francais'),
        'visual_style': _text('House visual style', 1000,
                              description='Merged into image and video descriptions.'),
        # Per language, how each place, faction and term of this world is rendered, so that
        # every translation says it the same way. Filled by the translator the first time a
        # term appears; a rendering written by the person is never replaced.
        'term_translations': {
            'type': 'object', 'default': {}, 'title': 'Translated terms',
            'additionalProperties': {'type': 'object', 'additionalProperties': {
                'type': 'object', 'additionalProperties': False, 'properties': {
                    'text': {'type': 'string', 'maxLength': 200},
                    'source': {'type': 'string', 'enum': ['model', 'person']},
                    'model': {'type': 'string', 'maxLength': 80},
                    'at': {'type': 'string', 'maxLength': 40}}}}},
        'created': _text('Created', 40),
        'modified': _text('Modified', 40),
        'revision': {'type': 'integer', 'minimum': 0, 'default': 0},
        'notes': _text('Private notes', 4000),
    },
}

# --------------------------------------------------------------------------- scene

# What the model is asked to emit next to its reply. Visible in the conversation and
# exploitable by an image/video tool; never spoken by the voice backend.
SCENE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'default': {},
    'properties': {
        'kind': {'type': 'string', 'default': 'cy.persona.scene'},
        'version': {'type': 'integer', 'default': 1},
        'persona_id': _text('Persona', 80),
        'persona_name': _text('Character', 120),
        'beat': _text('Beat', 200, description='One line naming the moment.'),
        'appearance': _text('Appearance in this shot', 2000),
        'pose': _text('Pose', 800),
        'expression': _text('Expression', 600),
        'action': _text('Action', 1200),
        'motion': {'type': 'array', 'default': [], 'maxItems': 32, 'title': 'Movement',
                   'items': _object('Movement beat', {
                       'at': {'type': 'number', 'minimum': 0.0, 'maximum': 600.0, 'default': 0.0},
                       'action': _text('Action', 600),
                   })},
        'camera': _object('Camera', {
            'shot': _text('Shot', 120),
            'angle': _text('Angle', 120),
            'lens': _text('Lens', 120),
            'movement': _text('Movement', 300),
        }),
        'setting': _object('Setting', {
            'location': _text('Location', 300),
            'time': _text('Time of day', 120),
            'weather': _text('Weather', 200),
            'lighting': _text('Lighting', 400),
            'background': _text('Background', 800),
        }),
        'mood': _text('Mood', 300),
        'duration_seconds': {'type': 'number', 'minimum': 0.0, 'maximum': 600.0, 'default': 0.0},
        'aspect_ratio': _text('Aspect ratio', 20),
        'image_prompt': _text('Image prompt', 3000),
        'video_prompt': _text('Video prompt', 3000),
        'negative_prompt': _text('Negative prompt', 1500),
        # Deliberately open: a later tool declares its own shape and the model fills it.
        'renderings': {'type': 'object', 'default': {},
                       'title': 'Tool-specific forms',
                       'additionalProperties': {'type': ['object', 'array', 'string']}},
    },
}


def normalize_persona(value):
    return validate_parameters(copy.deepcopy(value or {}), PERSONA_SCHEMA)


def normalize_world(value):
    return validate_parameters(copy.deepcopy(value or {}), WORLD_SCHEMA)


def normalize_scene(value):
    return validate_parameters(copy.deepcopy(value or {}), SCENE_SCHEMA)


def normalize_language_voice(value):
    return validate_parameters(copy.deepcopy(value or {}), LANGUAGE_VOICE_SCHEMA)


def normalize_stable_voice(value):
    return validate_parameters(copy.deepcopy(value or {}), STABLE_VOICE_SCHEMA)
