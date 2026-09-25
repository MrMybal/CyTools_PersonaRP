"""Deciding how a character's line should be spoken, and with which voice.

Three ways a character can have a voice, in the order they are preferred:

  1. a stable voice — a take captured once and cloned for every line afterwards;
  2. a written description — the VoiceDesign model invents a voice from it;
  3. a preset speaker — the CustomVoice model, steered by an instruction.

When the sheet asks for it, the standing voice direction is combined with what the
character is like and where the scene stands. The memory and the world lore are left out
on purpose: they are not delivery, they would only crowd a bounded instruction.
"""
from ..schemas import normalize_language_voice
from . import catalog, stable

MAX_INSTRUCTION = 2000

# Qwen3-TTS ships one set of weights per capability, and asking the wrong one produces a
# flat refusal from the model rather than a bad take. The mode decides the variant, always;
# a variant recorded on a sheet or a voice can only choose the size.
VARIANTS = {'custom': ('1.7B-CustomVoice', '0.6B-CustomVoice'),
            'clone': ('1.7B-Base', '0.6B-Base'),
            'design': ('1.7B-VoiceDesign',)}
DESIGN_VARIANT = '1.7B-VoiceDesign'
CLONE_VARIANT = '1.7B-Base'


def _clip(value, limit):
    value = ' '.join(str(value or '').split())
    return value[:limit]


def persona_instruction(persona, world=None, user_text='', scene=None):
    """A bounded acting direction built from the sheet and the moment, not from the lore."""
    voice = persona.get('voice') or {}
    parts = ['Acting direction only. Speak the supplied text and nothing else.']
    if voice.get('instruction'):
        parts.append('Standing direction: ' + _clip(voice['instruction'], 450))
    if not voice.get('use_persona_style', True):
        return '\n'.join(parts)[:MAX_INSTRUCTION]

    speech = persona.get('speech') or {}
    personality = persona.get('personality') or {}
    state = persona.get('state') or {}
    for label, value in (
            ('Character', persona.get('name')),
            ('Personality', personality.get('summary') or '; '.join(personality.get('traits') or [])),
            ('Speaking style', speech.get('style')),
            ('Register', speech.get('register')),
            ('Accent', speech.get('accent')),
            ('Mood right now', state.get('mood')),
            ('Where the scene is', state.get('location')),
            ('Tone of this world', (world or {}).get('tone'))):
        clipped = _clip(value, 180)
        if clipped:
            parts.append('%s: %s' % (label, clipped))
    if scene and scene.get('mood'):
        parts.append('Mood of this shot: ' + _clip(scene['mood'], 120))
    if user_text:
        parts.append('This line answers: ' + _clip(user_text, 200))
    return '\n'.join(parts)[:MAX_INSTRUCTION]


def _stable(identifier, voices=None):
    """A usable stable voice, or None with the reason why not.

    `voices` holds voices that live outside the library — those a batch task brought with
    its characters, already checked against their fingerprint. They are looked at first.
    """
    identifier = (identifier or '').strip()
    if not identifier:
        return None, ''
    if voices and identifier in voices:
        return voices[identifier], ''
    if not stable.exists(identifier):
        return None, 'The voice "%s" is not in the library.' % identifier
    check = stable.verify(identifier)
    if not check['ok']:
        return None, check['reason']
    return stable.get(identifier), ''


def resolve_voice(persona, voices=None):
    """The stable voice attached to this character, or None with the reason why not."""
    voice = persona.get('voice') or {}
    document, reason = _stable(voice.get('voice_id'), voices)
    if document is None and reason:
        reason += ' The character falls back to a preset speaker.'
    return document, reason


def native_language(persona, document=None):
    """The language the character's own lines are written in.

    The sheet decides; the language recorded on the stable voice is only a fallback, so the
    "Spoken language" shown on the sheet is the one that is really used.
    """
    chosen = (persona.get('voice') or {}).get('language') or 'Auto'
    if chosen == 'Auto' and document:
        chosen = document.get('language') or 'Auto'
    return chosen


def language_entry(persona, language):
    """The sheet's configuration for one language, or None when it has none."""
    for entry in (persona.get('voice') or {}).get('languages') or []:
        if entry.get('language') == language:
            return normalize_language_voice(entry)
    return None


def payload_for(persona, text, *, world=None, user_text='', scene=None, model='', device='cuda',
                seed=None, delivery='', language='', voices=None):
    """The worker request that speaks this line with this character's voice.

    `language` asks for the line in another language than the character's own — a
    translated line. The sheet's entry for that language decides which voice speaks it.

    `voices` are stable voices kept outside the library (see _stable).

    Returns (payload, note). The note is a plain-language remark for the interface when the
    requested voice could not be used exactly as asked; it never replaces an error. The
    payload's `voice_plan` says what was really chosen, for the interface and the outputs.
    """
    voice = persona.get('voice') or {}
    document, note = resolve_voice(persona, voices)
    native = native_language(persona, document)
    target = (language or '').strip() or native
    # Entries are for the other languages: one written for the character's own language would
    # otherwise replace the main voice on every ordinary line.
    entry = language_entry(persona, target) if target not in ('Auto', native) else None
    source = entry['source'] if entry else 'same'
    accent = entry['accent'] if entry else 'keep'
    instruction = persona_instruction(persona, world, user_text, scene)
    if entry and entry['instruction'].strip():
        instruction += '\nIn %s: %s' % (target, _clip(entry['instruction'], 450))

    def remark(text):
        nonlocal note
        note = (note + ' ' if note else '') + text

    if source == 'voice':
        other, reason = _stable(entry['voice_id'], voices)
        if other is None:
            remark((reason or 'No stable voice is chosen for %s.' % target)
                   + " The character's own voice was used instead.")
            source = 'same'
        else:
            document = other
    if source == 'design' and not entry['description'].strip():
        remark('No voice description is written for %s; the character\'s own voice was used.'
               % target)
        source = 'same'

    # Same arithmetic as before languages existed, so earlier takes stay reproducible.
    chosen_seed = seed
    if chosen_seed in (None, -1) and entry and entry['seed'] >= 0:
        chosen_seed = entry['seed']
    if chosen_seed is None:
        chosen_seed = (document or {}).get('seed', -1)
    payload = {
        'text': text,
        'language': target if target else 'Auto',
        'instruction': instruction,
        'annotations': bool(voice.get('annotations', True)),
        'delivery': delivery or voice.get('delivery', 'paragraphs'),
        'device': device,
        'seed': int(chosen_seed or 42) & 0x7fffffff,
    }

    # Which voice speaks, once the language has had its say.
    foreign = target not in ('Auto', native) and native != 'Auto'
    if source == 'same' and foreign and accent == 'keep':
        spoken_accent = 'Speak %s with the accent of a native %s speaker.' % (target, native)
    elif source == 'same' and foreign:
        spoken_accent = 'Pronounce %s the way a native speaker does.' % target
    else:
        spoken_accent = ''

    if source in ('same', 'voice') and document is not None:
        seed_value = payload['seed']
        payload.update(stable.clone_parameters(document))
        payload['seed'] = seed_value
        payload['language'] = target
        payload['instruction'] = instruction
        payload['mode'] = 'clone'
        # The in-context clone continues the take itself — its accent comes along. The
        # speaker embedding alone carries the timbre and leaves the pronunciation to the model.
        payload['x_vector_only'] = source == 'same' and accent == 'native'
        preferred = document.get('model') or model
    elif source == 'design' or (source == 'same' and (
            (voice.get('description') or '').strip() or model == DESIGN_VARIANT)):
        described = entry['description'] if source == 'design' else voice.get('description', '')
        payload['mode'] = 'design'
        payload['instruction'] = '\n'.join(part for part in (
            instruction, 'Voice to invent: ' + _clip(described, 400), spoken_accent)
            if part)[:MAX_INSTRUCTION]
        preferred = model
    else:
        payload['mode'] = 'custom'
        payload['speaker'] = (entry['speaker'] if source == 'preset' else '') \
            or voice.get('speaker') or 'Ryan'
        payload['instruction'] = '\n'.join(part for part in (instruction, spoken_accent)
                                           if part)[:MAX_INSTRUCTION]
        preferred = model or voice.get('model') or ''

    found, fallback = _model_for(payload['mode'], preferred)
    payload['model'] = found['id']
    payload['model_path'] = found['directory']
    if fallback:
        remark(fallback)
    payload['voice_plan'] = {
        'language': target, 'native': native, 'configured': entry is not None,
        'source': source, 'accent': accent if source == 'same' else '',
        'voice_id': (document or {}).get('id', '') if payload['mode'] == 'clone' else '',
        'speaker': payload.get('speaker', ''), 'mode': payload['mode']}
    return payload, note


def _model_for(mode, preferred=''):
    """The installed weights that can actually do this mode.

    Returns (entry, note). The note explains a substitution rather than letting the model
    refuse the request with a message about tokenizer types.
    """
    from cytools_core import CyToolError
    models = catalog.catalog()
    allowed = VARIANTS.get(mode, VARIANTS['custom'])

    def entry_for(variant):
        for key, info in models.items():
            if info.get('backend') == 'qwen3tts' and info.get('variant') == variant \
                    and catalog.installed(key):
                return {'id': key, 'directory': str(catalog.directory(key))}
        return None

    if preferred in allowed:
        found = entry_for(preferred)
        if found:
            return found, ''
    for variant in allowed:
        found = entry_for(variant)
        if found:
            note = ''
            if preferred and preferred not in allowed:
                note = ('"%s" cannot %s a voice, so %s was used instead.'
                        % (preferred, mode, variant))
            return found, note
    raise CyToolError(
        'MissingModel',
        'No installed speech model can %s a voice. Install %s in the Voice tab.'
        % (mode, ' or '.join(allowed)),
        details={'mode': mode, 'requires': list(allowed)})
