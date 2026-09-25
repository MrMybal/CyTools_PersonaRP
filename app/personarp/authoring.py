"""The creation assistant: ask the model for a sheet, a world, or one section of either.

The assistant never plays the character and never writes to the library. It returns a
proposal; applying it is a separate, explicit action, and applying a section replaces only
that section, so a generated appearance can never quietly wipe a memory you wrote by hand.
"""
import copy
import json
import re

from cytools_core import CyToolError

from .schemas import (PERSONA_SCHEMA, WORLD_SCHEMA, normalize_persona, normalize_world)

# Each target names the sheet branch it fills and the shape the model must return.
PERSONA_TARGETS = {
    'sheet': ('', 'the whole character'),
    'identity': ('identity', 'name, aliases, pronouns, age, species, summary and tags'),
    'appearance': ('appearance', 'the appearance branch'),
    'personality': ('personality', 'the personality branch'),
    'speech': ('speech', 'the speech branch'),
    'background': ('background', 'the background branch'),
    'state': ('state', 'the current-state branch'),
    'memory': ('memory', 'the memory branch'),
    'media': ('media', 'the visual-direction branch'),
    'dialogues': ('speech.example_dialogues', 'example dialogues, as plain text'),
    'notes': ('notes', 'private notes, as plain text'),
}
WORLD_TARGETS = {
    'world': ('', 'the whole world'),
    'setting': ('setting', 'the setting, as plain text'),
    'locations': ('locations', 'the list of locations'),
    'factions': ('factions', 'the list of factions'),
    'rules': ('rules', 'the list of laws of this world'),
    'history': ('history', 'the timeline'),
    'glossary': ('glossary', 'the glossary'),
    'canon': ('canon', 'the canon notes, as plain text'),
}

IDENTITY_KEYS = ('name', 'aliases', 'pronouns', 'age', 'species', 'summary', 'tags')

SYSTEM = (
    'You are a writing assistant for character sheets and worlds. You help invent coherent, '
    'specific, usable material. You never play the character, never address them, and never '
    'claim to have saved anything. Answer in the language of the request; default to French.')


# Reading a photograph takes two passes. A single pass constrained to JSON made a 7B vision
# model answer one word per field ("longue", "bleus"): the grammar lets it stop as soon as a
# field is technically filled. So the model first LOOKS — free prose, the form in which it is
# most precise — and then WRITES the sheet from its own observation, under a schema that asks
# for real phrases. The second pass is text only and reuses the model already loaded.

VISION_SYSTEM = (
    'You describe the appearance of a character from a photograph, for a character sheet. '
    'Report only what is visible in the image. Do not guess a name, a history or a '
    'personality, and do not comment on the picture itself.')

VISION_STRUCTURE_SYSTEM = (
    'You write the appearance section of a character sheet from an observation of a '
    'photograph. Use only what the observation states; do not guess a name, a history or a '
    'personality. Answer with the JSON object only.')

# What the vision pass fills. Strings and lists of strings only, so llama.cpp can compile it
# into a decoding grammar and the answer is parseable by construction.
VISION_FIELDS = ('summary', 'build', 'face', 'hair', 'eyes', 'skin', 'outfit', 'marks',
                 'accessories', 'age_reading', 'visual_tags', 'style_reference')

# What each field holds, told to the writing pass. A field that says what it is about is
# filled with that and not with a copy of its neighbour.
VISION_GUIDE = {
    'summary': 'one sentence someone could picture the person from: apparent age, how they '
               'present (as the observation says: a woman, a man…), and the two or three most '
               'striking features',
    'build': 'stature, build and posture — only if the body is visible',
    'face': 'shape of the face and its features: brows, nose, lips, cheekbones, jaw',
    'hair': 'colour with its nuance, length, texture, and how it is worn',
    'eyes': 'colour, shape, and the look in them',
    'skin': 'tone, texture, freckles, marks of age, make-up',
    'outfit': 'each garment with its colour, material, pattern and cut',
    'marks': 'scars, tattoos, piercings, birthmarks — only if visible',
    'accessories': 'jewellery, glasses, bags and straps, anything worn or carried',
    'age_reading': 'the apparent age range',
    'style_reference': 'the look of the picture itself: medium, light, lens, grain; empty '
                       'for an ordinary photograph',
}
# Minimum lengths of the fields a portrait almost always answers: long enough that a single
# word no longer satisfies the grammar, short enough that a sparse picture is not padded.
VISION_MINIMUM = {'summary': 40, 'hair': 12, 'eyes': 8, 'outfit': 20}


def vision_schema(fields=VISION_FIELDS):
    properties = {}
    for field in fields:
        if field.endswith('_tags'):
            # Twelve characters at least: "jeune femme" or "yeux bleus" are true of thousands
            # of people and no longer pass; "sacoche en cuir fauve" does.
            properties[field] = {'type': 'array', 'minItems': 6, 'maxItems': 12,
                                 'items': {'type': 'string', 'minLength': 12, 'maxLength': 60}}
        else:
            properties[field] = {'type': 'string', 'maxLength': 400}
            if field in VISION_MINIMUM:
                properties[field]['minLength'] = VISION_MINIMUM[field]
    # Every field is required, and only the four a portrait always shows have a minimum
    # length: the others may be an empty string. Optional fields were simply skipped — the
    # model stopped after the required ones although the observation described the face, the
    # skin and the accessories. Required but allowed empty, each one is considered, and one
    # the picture cannot answer (the build in a head-and-shoulders shot) stays empty rather
    # than invented, since the writing pass only has the observation to draw from.
    return {'type': 'object', 'additionalProperties': False, 'properties': properties,
            'required': list(fields)}


def observation_request(role='', caption=''):
    """First pass, with the photograph: look closely and say it in prose.

    In English, the language these models describe most precisely in; the sheet is written
    in its own language by the second pass.
    """
    lines = ['Look closely at the person in this photograph and describe their appearance in '
             'detail, in 150 to 300 words of plain prose, for a character sheet. Go through, in '
             'this order and only as far as the picture shows:',
             '- the overall impression: apparent age, how they present, build and posture;',
             '- the face: its shape, brows, eyes (colour, shape, the look in them), nose, lips, '
             'cheekbones, jaw, and the expression;',
             '- the skin: tone, texture, freckles, marks, make-up;',
             '- the hair: exact colour and its nuance, length, texture, how it is worn;',
             '- the clothes, garment by garment: colour, material, pattern, cut, how they are '
             'worn;',
             '- jewellery and accessories, straps, anything carried or held;',
             '- scars, tattoos, piercings;',
             '- in one last sentence, the look of the picture itself (light, background).',
             'Name colours precisely (charcoal, rust, ivory — not just dark or light) and say '
             'what you cannot see rather than guessing it.']
    if role and role != 'reference':
        lines.append('The picture is a ' + role.replace('_', ' ') + '.')
    if caption:
        lines.append('The owner of the sheet notes: ' + str(caption)[:300])
    return '\n'.join(lines)


def vision_request(role='', caption='', language='Francais', existing=None, observation=''):
    """Second pass, text only: the sheet written from the observation of the first."""
    lines = ['Write the appearance section of a character sheet for the person described '
             'below.']
    if observation:
        lines.append('Observation of the photograph:\n"""\n' + str(observation)[:6000]
                     + '\n"""')
    if role and role != 'reference':
        lines.append('The picture is a ' + role.replace('_', ' ') + '.')
    if caption:
        lines.append('The owner of the sheet notes: ' + str(caption)[:300])
    lines.append('Each field holds a descriptive phrase, not a single word:\n' + '\n'.join(
        '- %s: %s' % (field, guide) for field, guide in VISION_GUIDE.items()))
    # A 7B model will happily split a phrase into single words, and "woman" or "blue" in an
    # image prompt identifies nobody; a counter-example is what keeps the tags usable, since
    # the grammar can guarantee the shape but not the sense.
    # The example is deliberately a different person in a different register. An example that
    # could pass for a plausible answer gets copied verbatim instead of imitated — a 7B model
    # returned these very words for an unrelated photograph.
    lines.append(
        'visual_tags: six to twelve tags. Each tag is a noun phrase of three to six words '
        'naming one visible thing with what makes it theirs — a colour with a material or a '
        'pattern, a shape with a colour. They are repeated word for word in every image '
        'prompt of this character, so each one must identify them on its own. Each tag '
        'names a different thing: never two tags about the same garment or feature.\n'
        'Example of the FORM only, about someone else entirely — never reuse these words: '
        '["barbe blanche taillee court", "veste de pecheur ciree", "pipe en bruyere", '
        '"tatouage d ancre a l avant-bras"]\n'
        'Wrong, whoever is in the picture: ["homme", "vieux", "verte", "veste"] — single '
        'words describe no one in particular — and ["jeune femme", "yeux bleus", "cheveux '
        'longs"] — true of thousands of people.\n'
        'Do not put a mood, an action, a camera word or the picture quality in a tag.')
    lines.append('Answer every field. Fill it only with what that field is about, and only '
                 'with what the observation states. If it does not say — the build in a '
                 'head-and-shoulders shot, a scar — leave that field as an empty string. Never '
                 'repeat the same words in two different fields.')
    if existing:
        lines.append('The sheet already says: ' + json.dumps(existing, ensure_ascii=False)[:1200]
                     + '\nKeep what still matches the photograph and correct the rest.')
    lines.append('Write every value in %s only, in its own alphabet — not one word of another '
                 'language, even where the observation uses one.' % (language or 'Francais'))
    lines.append('Write the values in: ' + (language or 'Francais'))
    return '\n'.join(lines)


# Qwen vision models drift into Chinese mid-sentence now and then ("sans taches ou 雀斑"): the
# grammar guarantees the shape of the answer, not its alphabet. For a sheet written in a
# language that does not use these scripts, what slips through is removed.
_FOREIGN_SCRIPTS = re.compile('[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af'
                              '\uff00-\uffef]+')
_OWN_SCRIPTS = ('chinese', 'japanese', 'korean', 'chinois', 'japonais', 'coreen', 'coréen',
                'zh', 'ja', 'ko')


def clean_vision_fields(fields, language='Francais'):
    """Remove a script the sheet's language does not use and what it leaves dangling, a word
    stuttered twice ("menton fort fort"), and a tag given twice."""
    foreign = str(language or '').strip().lower() not in _OWN_SCRIPTS

    def clean(value):
        if isinstance(value, list):
            seen, kept = set(), []
            for item in (clean(entry) for entry in value):
                if item and item.casefold() not in seen:
                    seen.add(item.casefold())
                    kept.append(item)
            return kept
        if not isinstance(value, str):
            return value
        if foreign and _FOREIGN_SCRIPTS.search(value):
            value = _FOREIGN_SCRIPTS.sub(' ', value)
            value = re.sub(r'\s*\b(ou|et|or|and|y|o|und|oder)\s*([,.;]|$)', r'\2', value)
        # « nous nous », « vous vous » are French; any other word said twice is a stutter.
        value = re.sub(r'\b(?!(?:nous|vous)\b)(\w+)(\s+\1\b)+', r'\1', value,
                       flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', value).strip(' ,;')

    return {key: clean(value) for key, value in fields.items()}


def _grammar(node, depth=0):
    """A decoding-grammar-friendly copy of a schema branch: structure, nothing else.

    The sheet schemas carry titles, defaults and length limits that only bloat a grammar,
    and a deep one slows decoding for no gain. This keeps the shape.
    """
    kind = node.get('type')
    if 'enum' in node:
        return {'type': 'string', 'enum': list(node['enum'])}
    if kind == 'object' and depth < 3:
        properties = {key: _grammar(child, depth + 1)
                      for key, child in (node.get('properties') or {}).items()}
        if properties:
            # Nothing is required: the grammar is there to guarantee the answer parses, not
            # to force a model to fill sixty fields before it is allowed to stop.
            return {'type': 'object', 'additionalProperties': False,
                    'properties': properties, 'required': []}
    if kind == 'array':
        return {'type': 'array', 'minItems': 1, 'maxItems': min(node.get('maxItems', 12), 12),
                'items': _grammar(node.get('items') or {'type': 'string'}, depth + 1)}
    if kind in ('boolean', 'integer', 'number'):
        return {'type': kind}
    return {'type': 'string'}


def grammar_schema(target, kind='persona'):
    """Constrain an authoring answer, or None for a target that is plain text."""
    targets = PERSONA_TARGETS if kind == 'persona' else WORLD_TARGETS
    if target not in targets:
        raise CyToolError('InvalidParameters', 'Unknown authoring target: ' + str(target))
    dotted, _ = targets[target]
    root = PERSONA_SCHEMA if kind == 'persona' else WORLD_SCHEMA
    if target in ('sheet', 'world'):
        skip = {'format', 'schemaVersion', 'id', 'created', 'modified', 'revision', 'references'}
        if target == 'sheet':
            skip |= {'generation', 'voice', 'relationships', 'world_id'}
        properties = {key: _grammar(child) for key, child in root['properties'].items()
                      if key not in skip}
        return {'type': 'object', 'additionalProperties': False,
                'properties': properties, 'required': []}
    if target == 'identity':
        return {'type': 'object', 'additionalProperties': False, 'required': [],
                'properties': {key: _grammar(root['properties'][key]) for key in IDENTITY_KEYS}}
    branch = _branch_schema(root, dotted)
    if branch.get('type') not in ('object', 'array'):
        return None                                   # plain text: nothing to constrain
    return _grammar(branch)


def _branch_schema(root, dotted):
    node = root
    for part in [p for p in dotted.split('.') if p]:
        node = (node.get('properties') or {}).get(part)
        if node is None:
            raise CyToolError('InvalidParameters', 'Unknown target: ' + dotted)
    return node


def _shape(schema):
    """A compact description of the expected JSON, for the model to imitate."""
    kind = schema.get('type')
    if kind == 'object':
        return {key: _shape(child) for key, child in (schema.get('properties') or {}).items()}
    if kind == 'array':
        item = schema.get('items') or {'type': 'string'}
        return [_shape(item)]
    if kind == 'number':
        return 0.0
    if kind == 'integer':
        return 0
    if kind == 'boolean':
        return False
    return schema.get('title', 'text')


def parameters(request, target, current=None, kind='persona', language='Francais'):
    """Build the generate() parameters for one authoring request."""
    targets = PERSONA_TARGETS if kind == 'persona' else WORLD_TARGETS
    if target not in targets:
        raise CyToolError('InvalidParameters', 'Unknown authoring target: ' + str(target))
    dotted, label = targets[target]
    root = PERSONA_SCHEMA if kind == 'persona' else WORLD_SCHEMA

    if target == 'sheet':
        shape = {key: _shape(child) for key, child in root['properties'].items()
                 if key not in ('format', 'schemaVersion', 'id', 'created', 'modified',
                                'revision', 'generation', 'voice', 'relationships', 'world_id')}
    elif target == 'world':
        shape = {key: _shape(child) for key, child in root['properties'].items()
                 if key not in ('format', 'schemaVersion', 'id', 'created', 'modified', 'revision')}
    elif target == 'identity':
        shape = {key: _shape(root['properties'][key]) for key in IDENTITY_KEYS}
    else:
        shape = _shape(_branch_schema(root, dotted))

    plain = isinstance(shape, str)
    system = [SYSTEM, 'Write ' + label + '.']
    if plain:
        system.append('Answer with the text itself only. No preamble, no markdown fence, no JSON.')
    else:
        system.append('Answer with one valid JSON object and nothing else. No markdown fence, no '
                      'commentary. Every key below is optional: omit what you have nothing for, '
                      'never invent new keys.')
        system.append('Expected shape:\n' + json.dumps(shape, ensure_ascii=False, indent=2))
        system.append('Be concrete and specific. Short entries in lists, one idea each.')
    system.append('Response language: ' + (language or 'Francais'))

    context = {}
    if current:
        context = {k: v for k, v in current.items()
                   if k not in ('format', 'schemaVersion', 'created', 'modified', 'revision') and v}
    text = request.strip()
    if context:
        text += '\n\nExisting document, for consistency:\n' + json.dumps(context, ensure_ascii=False)[:6000]
    return {'text': text, 'system': '\n\n'.join(system), 'plain': plain, 'target': target,
            'kind': kind, 'dotted': dotted}


def parse_proposal(text, target, kind='persona'):
    """Read what the model returned; tolerate a fence, refuse anything not in the schema."""
    targets = PERSONA_TARGETS if kind == 'persona' else WORLD_TARGETS
    if target not in targets:
        raise CyToolError('InvalidParameters', 'Unknown authoring target: ' + str(target))
    dotted, _ = targets[target]
    root = PERSONA_SCHEMA if kind == 'persona' else WORLD_SCHEMA
    schema = root if target in ('sheet', 'world') else (
        {'type': 'object', 'properties': {k: root['properties'][k] for k in IDENTITY_KEYS}}
        if target == 'identity' else _branch_schema(root, dotted))

    body = text.strip()
    if schema.get('type') not in ('object', 'array'):
        return body
    if body.startswith('```'):
        if '\n' not in body:
            raise CyToolError('InvalidResponse', 'Incomplete proposal. Generate another one.')
        body = body.split('\n', 1)[1]
        if '```' in body:
            body = body.rsplit('```', 1)[0]
        body = body.strip()
    start, end = body.find('{' if schema['type'] == 'object' else '['), body.rfind('}' if schema['type'] == 'object' else ']')
    if start >= 0 and end > start:
        body = body[start:end + 1]
    try:
        document = json.loads(body)
    except ValueError as exc:
        raise CyToolError('InvalidResponse', 'The proposal is not valid JSON: ' + str(exc)) from exc
    if schema['type'] == 'object':
        if not isinstance(document, dict):
            raise CyToolError('InvalidResponse', 'Expected a JSON object.')
        allowed = set(schema.get('properties') or {})
        document = {k: v for k, v in document.items() if k in allowed}
        if not document:
            raise CyToolError('InvalidResponse', 'The proposal contained no usable field.')
    elif not isinstance(document, list):
        raise CyToolError('InvalidResponse', 'Expected a JSON array.')
    return document


def apply_proposal(document, proposal, target, kind='persona'):
    """Merge a proposal into a sheet without touching anything outside its target."""
    targets = PERSONA_TARGETS if kind == 'persona' else WORLD_TARGETS
    dotted, _ = targets[target]
    result = copy.deepcopy(document or {})
    if target in ('sheet', 'world'):
        for key, value in (proposal or {}).items():
            if key in ('id', 'created', 'modified', 'revision', 'format', 'schemaVersion'):
                continue
            result[key] = value
    elif target == 'identity':
        for key in IDENTITY_KEYS:
            if key in proposal:
                result[key] = proposal[key]
    else:
        parts = dotted.split('.')
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = proposal
    return normalize_persona(result) if kind == 'persona' else normalize_world(result)
