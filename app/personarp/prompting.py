"""Turning a character sheet, a world and a history into the prompt the model receives.

The sheet is deliberately large; a context window is not. Sections are assembled in
priority order and the ones that do not fit are dropped from the *prompt only* — the saved
sheet and the saved conversation are never modified. What was dropped is reported back so
the interface can say so instead of silently degrading the character.
"""
import json

from .scene import split_reply, spoken_text
from .schemas import normalize_persona, normalize_world

ROLE_USER = 'user'
ROLE_ASSISTANT = 'assistant'


def _bullets(title, values, limit=None):
    items = [str(v).strip() for v in (values or []) if str(v or '').strip()]
    if limit:
        items = items[:limit]
    return (title + ': ' + '; '.join(items)) if items else ''


def _field(title, value):
    value = str(value or '').strip()
    return (title + ': ' + value) if value else ''


def _block(title, lines):
    body = [line for line in lines if line]
    return (title + '\n' + '\n'.join(body)) if body else ''


def identity_section(persona):
    return _block('# Character', [
        _field('Name', persona.get('name')),
        _bullets('Also called', persona.get('aliases')),
        _field('Pronouns', persona.get('pronouns')),
        _field('Age', persona.get('age')),
        _field('Kind', persona.get('species')),
        _field('In short', persona.get('summary')),
        _field('Occupation', (persona.get('background') or {}).get('occupation')),
    ])


def personality_section(persona):
    p = persona.get('personality') or {}
    return _block('# Personality', [
        _field('Summary', p.get('summary')),
        _bullets('Traits', p.get('traits')),
        _bullets('Values', p.get('values')),
        _bullets('Wants', p.get('desires')),
        _bullets('Fears', p.get('fears')),
        _bullets('Flaws', p.get('flaws')),
        _bullets('Quirks', p.get('quirks')),
        _field('Humour', p.get('humour')),
        _field('Temperament', p.get('temperament')),
        _field('Moral compass', p.get('moral_compass')),
    ])


# Example lines steer a roleplay model's voice better than any description of it, but a long
# set would crowd out the sheet; this much is kept, cut at a line break.
EXAMPLE_DIALOGUE_LIMIT = 1500


def _examples(text):
    text = str(text or '').strip()
    if len(text) <= EXAMPLE_DIALOGUE_LIMIT:
        return text
    cut = text.rfind('\n', 0, EXAMPLE_DIALOGUE_LIMIT)
    return text[:cut if cut > 0 else EXAMPLE_DIALOGUE_LIMIT].rstrip()


def speech_section(persona):
    s = persona.get('speech') or {}
    examples = _examples(s.get('example_dialogues'))
    return _block('# Voice on the page', [
        _field('Speaking style', s.get('style')),
        _field('Register', s.get('register')),
        _field('Vocabulary', s.get('vocabulary')),
        _field('Accent', s.get('accent')),
        _bullets('Verbal tics', s.get('verbal_tics')),
        _bullets('Catchphrases', s.get('catchphrases')),
        _bullets('Languages', s.get('languages')),
        _field('Narration style', s.get('narration_style')),
        ('Example lines — how this character sounds; a reference for tone, never lines to '
         'repeat:\n' + examples) if examples else '',
    ])


def appearance_section(persona):
    a = persona.get('appearance') or {}
    return _block('# Appearance', [
        _field('At a glance', a.get('summary')),
        _field('Build', a.get('build')),
        _field('Face', a.get('face')),
        _field('Hair', a.get('hair')),
        _field('Eyes', a.get('eyes')),
        _field('Skin', a.get('skin')),
        _field('Usual outfit', a.get('outfit')),
        _field('Marks', a.get('marks')),
        _field('Accessories', a.get('accessories')),
        _bullets('Visual tags', a.get('visual_tags')),
    ])


def background_section(persona):
    b = persona.get('background') or {}
    return _block('# Background', [
        _field('Origin', b.get('origin')),
        _field('Story', b.get('story')),
        _bullets('Skills', b.get('skills')),
        _bullets('Possessions', b.get('possessions')),
        _bullets('Factions', b.get('factions')),
        _field('Secrets (known to you, revealed only if the scene earns it)', b.get('secrets')),
    ])


def memory_section(persona):
    m = persona.get('memory') or {}
    episodes = sorted((m.get('episodes') or []),
                      key=lambda e: (not e.get('pinned'), -float(e.get('weight', 0.5))))
    lines = [_bullets('Facts', m.get('facts'))]
    for episode in episodes[:24]:
        when = str(episode.get('when') or '').strip()
        summary = str(episode.get('summary') or '').strip()
        if summary:
            lines.append('- ' + (when + ' — ' if when else '') + summary)
    return _block('# What this character remembers', lines)


def state_section(persona):
    s = persona.get('state') or {}
    return _block('# Right now', [
        _field('Scene', s.get('scenario')),
        _field('Location', s.get('location')),
        _field('Time', s.get('time')),
        _field('Mood', s.get('mood')),
        _field('Condition', s.get('energy')),
        _field('Wearing', s.get('outfit_now')),
        _bullets('Immediate goals', s.get('goals')),
        _bullets('Open tensions', s.get('tensions')),
    ])


def relations_section(persona, others=None):
    """Who else exists and how this character feels about them."""
    known = {entry['id']: entry for entry in (others or [])}
    lines = []
    for relation in persona.get('relationships') or []:
        name = relation.get('name') or known.get(relation.get('persona_id'), {}).get('name') \
            or relation.get('persona_id') or 'someone'
        head = name
        if relation.get('label'):
            head += ' (calls them "%s")' % relation['label']
        details = [_field('bond', relation.get('type')),
                   'feeling %+.2f' % float(relation.get('sentiment', 0.0)),
                   'trust %.2f' % float(relation.get('trust', 0.5))]
        if not relation.get('known', True):
            details.append('they have not actually met')
        lines.append('- ' + head + ' — ' + ', '.join(d for d in details if d))
        if relation.get('history'):
            lines.append('  history: ' + relation['history'])
        if relation.get('tension'):
            lines.append('  tension: ' + relation['tension'])
        if relation.get('secret'):
            lines.append('  keeps from them: ' + relation['secret'])
    return _block('# Relationships', lines)


def world_section(world):
    if not world:
        return ''
    lines = [
        _field('World', world.get('name')),
        _field('Pitch', world.get('summary')),
        _field('Genre', world.get('genre')),
        _field('Tone', world.get('tone')),
        _field('Era', world.get('era')),
        _field('Setting', world.get('setting')),
    ]
    for location in (world.get('locations') or [])[:20]:
        if location.get('name'):
            lines.append('- Place · %s: %s' % (location['name'], location.get('description', '')))
    for faction in (world.get('factions') or [])[:20]:
        if faction.get('name'):
            lines.append('- Faction · %s: %s' % (faction['name'], faction.get('description', '')))
    for rule in (world.get('rules') or [])[:20]:
        if rule.get('name'):
            lines.append('- Law · %s: %s' % (rule['name'], rule.get('description', '')))
    for event in (world.get('history') or [])[:20]:
        if event.get('what'):
            lines.append('- %s: %s' % (event.get('when', 'once'), event['what']))
    for term in (world.get('glossary') or [])[:40]:
        if term.get('term'):
            lines.append('- Term · %s: %s' % (term['term'], term.get('meaning', '')))
    lines.append(_field('Canon', world.get('canon')))
    lines.append(_field('Never happens here', world.get('forbidden')))
    lines.append(_field('House narration', world.get('narration_style')))
    return _block('# Shared world', lines)


def cast_section(others):
    """The rest of the cast, so the character can mention them without inventing them."""
    lines = []
    for entry in others or []:
        summary = str(entry.get('summary') or '').strip()
        lines.append('- ' + entry.get('name', entry.get('id', '?')) + (': ' + summary if summary else ''))
    return _block('# Others in this world', lines)


ANNOTATION_RULES = (
    '# Voice annotations\n'
    'You may mark delivery inline with square brackets: [tone: hushed], [emotion: relief], '
    '[pause: 400ms], [rate: slow], [volume: whisper], [emphasis: never]. They steer the voice '
    'and are not pronounced. Use them sparingly, only where the delivery would otherwise be '
    'misread. Never annotate a whole paragraph.'
)


def scene_rules(media):
    """The instruction that produces the machine-readable movement/image/video description."""
    detail = (media or {}).get('detail', 'standard')
    shape = {
        'kind': 'cy.persona.scene',
        'beat': 'one line naming the moment',
        'appearance': 'how the character looks in this shot',
        'pose': 'body position',
        'expression': 'face',
        'action': 'what happens, one sentence',
        'motion': [{'at': 0.0, 'action': 'first movement'},
                   {'at': 1.5, 'action': 'next movement'}],
        'camera': {'shot': 'medium shot', 'angle': 'eye level', 'lens': '50mm',
                   'movement': 'slow push in'},
        'setting': {'location': '', 'time': '', 'weather': '', 'lighting': '', 'background': ''},
        'mood': '',
        'duration_seconds': float((media or {}).get('duration_seconds', 5.0)),
        'aspect_ratio': (media or {}).get('aspect_ratio', '16:9'),
        'image_prompt': 'one self-contained sentence describing the still',
        'video_prompt': 'one self-contained sentence describing the clip',
        'negative_prompt': 'what must not appear',
    }
    if detail == 'minimal':
        for key in ('motion', 'camera', 'setting', 'mood', 'aspect_ratio', 'negative_prompt'):
            shape.pop(key, None)
    extra = [t for t in ((media or {}).get('extra_targets') or []) if str(t).strip()]
    if extra:
        shape['renderings'] = {str(name): {'prompt': 'form expected by ' + str(name)}
                               for name in extra[:6]}
    lines = [
        '# Scene directive',
        'After your reply, and only after it, add one fenced block tagged `scene` containing a '
        'single JSON object describing what a camera would see. It is read by image and video '
        'tools; it is never spoken and never part of your dialogue. Describe only — do not '
        'attempt to draw or render anything.',
        'Use exactly this shape, keeping the keys and dropping the ones you have nothing for:',
        '```scene',
        json.dumps(shape, ensure_ascii=False, indent=2),
        '```',
        'Reuse the visual tags from the sheet verbatim so the character stays recognisable '
        'between shots.',
    ]
    if detail == 'full':
        lines.append('Be specific about light, lens and movement; a renderer will follow this '
                     'literally.')
    return '\n'.join(lines)


def behaviour_rules(persona):
    generation = persona.get('generation') or {}
    lines = []
    if generation.get('stay_in_character', True):
        lines.append('Stay in character for the whole scene. Never speak, decide or act for the '
                     'user. Never describe yourself as an assistant or a model.')
    if not generation.get('allow_narration', True):
        lines.append('Write dialogue only, with no narration.')
    if generation.get('behaviour_rules'):
        lines.append(generation['behaviour_rules'])
    return _block('# Rules', lines)


# Lowest priority first: this is the order sections are dropped in when the budget is tight.
DROP_ORDER = ['cast', 'world', 'background', 'memory', 'appearance', 'relations',
              'personality', 'speech', 'state']


def build_system_prompt(persona, world=None, others=None, budget=8192):
    """Assemble the system prompt, trimming from the least essential end when needed."""
    persona = normalize_persona(persona)
    world = normalize_world(world) if world else None
    generation = persona['generation']
    media = persona['media']
    voice = persona['voice']

    head = [generation.get('system_prompt') or '', 'Reply in: ' + (generation.get('language') or 'Francais')]
    if persona.get('enabled', True):
        head.append('You are playing the character below. Everything in these sections is true '
                    'of them.')
    sections = {
        'identity': identity_section(persona),
        'personality': personality_section(persona),
        'speech': speech_section(persona),
        'appearance': appearance_section(persona),
        'background': background_section(persona),
        'memory': memory_section(persona),
        'state': state_section(persona),
        'relations': relations_section(persona, others),
        'world': world_section(world),
        'cast': cast_section(others),
    }
    tail = [behaviour_rules(persona)]
    if voice.get('enabled') and voice.get('annotations'):
        tail.append(ANNOTATION_RULES)
    # In director mode the directive comes from a separate constrained pass, so the roleplay
    # prompt stays free of JSON instructions the character would otherwise try to obey.
    if media.get('enabled') and media.get('mode', 'director') == 'inline':
        tail.append(scene_rules(media))

    fixed = len('\n\n'.join(x for x in head + tail if x))
    dropped = []
    order = ['identity'] + [k for k in DROP_ORDER]
    while True:
        body = '\n\n'.join(sections[k] for k in order if sections.get(k))
        if fixed + len(body) <= budget or len(order) <= 1:
            break
        for candidate in DROP_ORDER:
            if candidate in order and sections.get(candidate):
                order.remove(candidate)
                dropped.append(candidate)
                break
        else:
            break
    body = '\n\n'.join(sections[k] for k in order if sections.get(k))
    prompt = '\n\n'.join(x for x in (head + [body] + tail) if x)
    return {'prompt': prompt, 'dropped': dropped, 'characters': len(prompt)}


DIRECTOR_SYSTEM = (
    'You are a storyboard director. You are given a character, a setting and the line that was '
    'just played. You describe what a camera would see: appearance, pose, expression, movement, '
    'framing and light. You never write dialogue, never continue the story, and never speak as '
    'the character. Answer with the JSON object only.')


def director_messages(persona, reply, user_text='', world=None):
    """The second pass: turn a played line into a machine-readable shot description.

    It receives only what a camera needs — the visual identity of the character, the house
    style of the world, where the scene stands, and the line itself. The memory, the secrets
    and the conversation history are not visual facts and are deliberately left out.
    """
    persona = normalize_persona(persona)
    appearance = persona['appearance']
    media = persona['media']
    state = persona['state']
    lines = [
        _field('Character', persona.get('name')),
        _field('Appearance', appearance.get('summary')),
        _field('Usual outfit', appearance.get('outfit')),
        _field('Currently wearing', state.get('outfit_now')),
        _bullets('Visual tags to reuse verbatim', appearance.get('visual_tags')),
        _bullets('Must not appear', appearance.get('negative_tags')),
        _field('Rendering style', appearance.get('style_reference')),
        _field('House visual style', (world or {}).get('visual_style')),
        _field('Location', state.get('location') or (world or {}).get('name')),
        _field('Time', state.get('time')),
        _field('Mood', state.get('mood')),
        _field('Movement style', media.get('motion_style')),
        _field('Default framing', media.get('default_shot')),
        _field('Camera notes', media.get('camera_notes')),
        _field('Clip length in seconds', media.get('duration_seconds')),
    ]
    if user_text:
        lines.append(_field('The other person just said', user_text[:600]))
    facts = '\n'.join(line for line in lines if line)
    played = spoken_text(reply, keep_annotations=False, speak_narration=True)[:4000]
    body = (facts + '\n\nThe line that was just played:\n' + played
            + '\n\nDescribe this single moment. image_prompt and video_prompt must each be one '
              'self-contained sentence a rendering tool can use on its own, including the visual '
              'tags. Keep every field short and concrete.')
    return [{'role': 'system', 'content': DIRECTOR_SYSTEM},
            {'role': ROLE_USER, 'content': body}]


def trim_history(history, budget):
    """Keep the most recent exchanges that fit; report how many were left out."""
    kept, used, dropped = [], 0, 0
    for item in reversed(history or []):
        size = len(str(item.get('content', ''))) + 16
        if used + size > budget and kept:
            dropped = len(history) - len(kept)
            break
        kept.append(item)
        used += size
    kept.reverse()
    return kept, dropped


def history_for_model(history, voice=None):
    """Past turns as the model should see them: no scene JSON, no delivery marks.

    A directive that went back into the context would teach the model to keep repeating it
    verbatim; the saved conversation keeps it, the prompt does not.
    """
    items = []
    for item in history or []:
        content = str(item.get('content', ''))
        if item.get('role') == ROLE_ASSISTANT:
            # Drop the fenced directive first: left in place it would be re-read as an
            # example and the model would start answering in JSON.
            content = split_reply(content)['text']
            content = spoken_text(content, keep_annotations=False, speak_narration=True)
        if content.strip():
            items.append({'role': item.get('role', ROLE_USER), 'content': content})
    return items


def messages(persona, text, history=None, world=None, others=None):
    """The full message list, plus what had to be left out of the prompt."""
    persona = normalize_persona(persona)
    budget = int((persona['generation'] or {}).get('context_budget', 8192))
    system = build_system_prompt(persona, world, others, budget=int(budget * 0.7))
    remaining = max(512, budget - system['characters'])
    trimmed, dropped_messages = trim_history(history_for_model(history), remaining)
    items = [{'role': 'system', 'content': system['prompt']}, *trimmed,
             {'role': ROLE_USER, 'content': text}]
    return {'messages': items,
            'context': {'droppedSections': system['dropped'],
                        'droppedMessages': dropped_messages,
                        'promptCharacters': system['characters'],
                        'budget': budget}}


def chatml(items):
    """Escape literal control tokens in content; only this function inserts role boundaries."""
    def escape(value):
        return str(value).replace('<|', '< |').replace('|>', '| >')
    return ''.join('<|im_start|>' + item['role'] + '\n' + escape(item['content']) + '<|im_end|>\n'
                   for item in items) + '<|im_start|>assistant\n'
