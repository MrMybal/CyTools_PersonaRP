"""Reading a reply back: dialogue, voice annotations, and the scene directive.

A reply carries three things at once and they must not be confused:

  * the line the character says, which is what the voice backend speaks;
  * voice annotations written inline, like [tone: hushed] or [pause: 400ms], which steer
    the delivery and are never pronounced;
  * an optional scene directive, a JSON object in a ```scene fence describing appearance,
    pose, movement, camera and setting. It stays visible in the conversation because it is
    the raw material for an image or video tool, and it is never spoken.

Everything here is tolerant: a model that forgets the fence, writes ```json instead, or
emits malformed JSON must degrade to "no directive", never to a failed reply.
"""
import json
import re

from .marks import ANNOTATION, BARE_VALUES, DURATION, KINDS, NARRATION, duration_ms, tidy
from .schemas import SCENE_SCHEMA, normalize_scene

SCENE_KEYS = frozenset(SCENE_SCHEMA['properties'])

FENCE = re.compile(r'```[ \t]*(scene|json|cy\.persona\.scene)?[ \t]*\r?\n(.*?)(?:```|\Z)',
                   re.DOTALL | re.IGNORECASE)


def split_reply(text, expect_scene=False):
    """Separate the spoken/written reply from its scene directive.

    Returns dialogue, the validated directive (or None), the raw block as the model wrote
    it, and a human-readable reason when a block was present but unusable.
    """
    text = text or ''
    best = None
    for match in FENCE.finditer(text):
        body = match.group(2).strip()
        if not body.startswith('{'):
            continue
        tag = (match.group(1) or '').lower()
        if tag in ('scene', 'cy.persona.scene') or expect_scene or '"kind"' in body:
            best = match
            break
        if best is None:
            best = match
    if best is None:
        # Some models drop the fence entirely and end on a bare object.
        tail = re.search(r'(\{\s*"kind"\s*:\s*"cy\.persona\.scene".*\})\s*\Z', text, re.DOTALL)
        if not tail:
            return {'text': text.strip(), 'scene': None, 'raw_scene': '', 'scene_error': ''}
        dialogue = text[:tail.start()].strip()
        raw = tail.group(1)
    else:
        dialogue = (text[:best.start()] + '\n' + text[best.end():]).strip()
        raw = best.group(2).strip()

    try:
        document = json.loads(raw)
    except ValueError as exc:
        return {'text': dialogue or text.strip(), 'scene': None, 'raw_scene': raw,
                'scene_error': 'Scene directive is not valid JSON: ' + str(exc)}
    if not isinstance(document, dict):
        return {'text': dialogue or text.strip(), 'scene': None, 'raw_scene': raw,
                'scene_error': 'Scene directive must be a JSON object.'}
    document.setdefault('kind', 'cy.persona.scene')
    unknown = set(document) - set(normalize_scene({}))
    for key in unknown:
        document.pop(key, None)
    try:
        scene = normalize_scene(document)
    except Exception as exc:                                   # noqa: BLE001 - reported, not raised
        return {'text': dialogue or text.strip(), 'scene': None, 'raw_scene': raw,
                'scene_error': str(exc)}
    note = ('Ignored unknown scene fields: ' + ', '.join(sorted(unknown))) if unknown else ''
    return {'text': dialogue, 'scene': scene, 'raw_scene': raw, 'scene_error': note}


def director_schema(media=None):
    """A constrained schema for the director pass, kept simple enough to compile to a grammar.

    llama.cpp turns this into a decoding grammar, so the reply cannot come back malformed.
    Unions, null types and unbounded objects are avoided on purpose; `renderings` is added
    only when the sheet actually names extra targets, because an open object cannot be
    constrained.
    """
    detail = (media or {}).get('detail', 'standard')
    string = {'type': 'string'}
    schema = {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'beat': string, 'appearance': string, 'pose': string, 'expression': string,
            'action': string, 'mood': string,
            'motion': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                       'items': {'type': 'object', 'additionalProperties': False,
                                 'properties': {'at': {'type': 'number'}, 'action': string},
                                 'required': ['at', 'action']}},
            'camera': {'type': 'object', 'additionalProperties': False,
                       'properties': {'shot': string, 'angle': string, 'lens': string,
                                      'movement': string},
                       'required': ['shot', 'angle', 'movement']},
            'setting': {'type': 'object', 'additionalProperties': False,
                        'properties': {'location': string, 'time': string, 'weather': string,
                                       'lighting': string, 'background': string},
                        'required': ['location', 'lighting']},
            'image_prompt': string, 'video_prompt': string, 'negative_prompt': string,
        },
        'required': ['beat', 'appearance', 'pose', 'expression', 'action', 'motion', 'camera',
                     'setting', 'image_prompt', 'video_prompt'],
    }
    if detail == 'minimal':
        for key in ('motion', 'setting', 'mood', 'negative_prompt'):
            schema['properties'].pop(key, None)
        schema['required'] = ['beat', 'appearance', 'pose', 'expression', 'action', 'camera',
                              'image_prompt', 'video_prompt']
    extra = [str(t).strip() for t in ((media or {}).get('extra_targets') or []) if str(t).strip()]
    if extra:
        schema['properties']['renderings'] = {
            'type': 'object', 'additionalProperties': False,
            'properties': {name: {'type': 'object', 'additionalProperties': False,
                                  'properties': {'prompt': string}, 'required': ['prompt']}
                           for name in extra[:6]},
            'required': extra[:6]}
    return schema


def sanitize_directive(document):
    """Make a generated directive fit the schema instead of throwing it away.

    A decoding grammar guarantees the *shape*, not the ranges: a model will happily emit a
    negative timestamp or a 900-second clip. Those are clamped here, because losing a whole
    shot description over one out-of-range float would be absurd.
    """
    value = dict(document or {})
    value['kind'] = 'cy.persona.scene'

    def clamp(number, low, high, fallback=0.0):
        try:
            return min(high, max(low, float(number)))
        except (TypeError, ValueError):
            return fallback

    beats = []
    for beat in value.get('motion') or []:
        if isinstance(beat, dict) and str(beat.get('action', '')).strip():
            beats.append({'at': clamp(beat.get('at', 0.0), 0.0, 600.0),
                          'action': str(beat['action'])[:600]})
    if beats:
        value['motion'] = sorted(beats, key=lambda b: b['at'])[:32]
    else:
        value.pop('motion', None)
    if 'duration_seconds' in value:
        value['duration_seconds'] = clamp(value['duration_seconds'], 0.0, 600.0, 5.0)
    for key in list(value):
        if key not in SCENE_KEYS:
            value.pop(key)
    return normalize_scene(value)


def parse_annotations(text):
    """Every recognised annotation with its canonical kind, value and position."""
    found = []
    for match in ANNOTATION.finditer(text or ''):
        name = (match.group(1) or '').strip().lower()
        kind = KINDS.get(name)
        if not kind:
            continue
        value = (match.group(2) or '').strip()
        if not value:
            value = BARE_VALUES.get(name, name)
        entry = {'kind': kind, 'name': name, 'value': value,
                 'start': match.start(), 'end': match.end()}
        if kind == 'pause':
            entry['milliseconds'] = duration_ms(value) or 300
        found.append(entry)
    return found


def strip_annotations(text):
    """The reply as a reader should see it, with the delivery marks taken out."""
    def replace(match):
        return '' if KINDS.get((match.group(1) or '').strip().lower()) else match.group(0)
    return tidy(ANNOTATION.sub(replace, text or ''))


def strip_narration(text):
    """Drop *stage directions* so the voice speaks dialogue only."""
    return tidy(NARRATION.sub('', text or ''))


def spoken_text(reply, keep_annotations=True, speak_narration=True):
    """What the voice backend receives.

    The scene directive is already gone by construction — this only ever sees `dialogue`.
    Annotations are kept when the backend understands them and removed otherwise, so an
    unsupported backend never pronounces "tone colon hushed".
    """
    value = reply or ''
    if not speak_narration:
        value = strip_narration(value)
    if not keep_annotations:
        value = strip_annotations(value)
    return re.sub(r'\n{3,}', '\n\n', tidy(value)).strip()


def scene_summary(scene):
    """One readable line for the transcript, above the folded JSON."""
    if not scene:
        return ''
    parts = [scene.get('beat') or scene.get('action') or '']
    camera = scene.get('camera') or {}
    setting = scene.get('setting') or {}
    if camera.get('shot'):
        parts.append(camera['shot'])
    if setting.get('location'):
        parts.append(setting['location'])
    if scene.get('duration_seconds'):
        parts.append('%.1fs' % scene['duration_seconds'])
    return ' · '.join(x for x in parts if x)


def to_prompts(scene, persona=None, world=None):
    """Fill image/video prompts from the structured fields when the model left them empty.

    The structured object stays the source of truth; this only makes the directive usable
    straight away by a tool that wants a single prompt string.
    """
    if not scene:
        return {'image_prompt': '', 'video_prompt': '', 'negative_prompt': ''}
    scene = dict(scene)
    appearance = (persona or {}).get('appearance') or {}
    camera = scene.get('camera') or {}
    setting = scene.get('setting') or {}

    def joined(*values):
        return ', '.join(str(v).strip() for v in values if str(v or '').strip())

    subject = joined(scene.get('persona_name') or (persona or {}).get('name', ''),
                     scene.get('appearance') or appearance.get('summary', ''),
                     *(appearance.get('visual_tags') or []))
    place = joined(setting.get('location'), setting.get('time'), setting.get('weather'),
                   setting.get('lighting'), setting.get('background'))
    style = joined(appearance.get('style_reference'), (world or {}).get('visual_style'))
    shot = joined(camera.get('shot'), camera.get('angle'), camera.get('lens'))

    image = scene.get('image_prompt') or joined(subject, scene.get('pose'),
                                                scene.get('expression'), place, shot, style)
    motion = joined(*(beat.get('action', '') for beat in scene.get('motion') or []))
    video = scene.get('video_prompt') or joined(subject, scene.get('action'), motion, place,
                                                camera.get('movement'), shot, style)
    negative = scene.get('negative_prompt') or joined(*(appearance.get('negative_tags') or []))
    return {'image_prompt': image, 'video_prompt': video, 'negative_prompt': negative}
