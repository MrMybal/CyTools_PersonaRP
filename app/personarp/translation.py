"""Translating a scene after it was played, so it can be heard in another language.

A scene is written once, in the character's own language. A translation is stored beside
each turn instead of replacing it: the original stays the reference, and one scene can
carry several languages at once, each with its own takes.

The delivery marks — [tone: …], [pause: 1s] — are directions for the voice, not words. They
are masked before the model reads the text and put back afterwards, so a translation can
neither translate them into something the voice would pronounce nor invent new ones. A
mark the model drops is reported; it is never guessed back into place.

The answer is constrained to one string per turn, which is what lets a whole scene be
translated in a few requests without any parsing of free text.
"""
import json
import re

from cytools_core import CyToolError

from .marks import ANNOTATION, tidy
from .schemas import LANGUAGES

TOKEN = '⟦%d⟧'
TOKEN_PATTERN = re.compile(r'⟦\s*(\d{1,3})\s*⟧')
# One request carries at most this much source text. A 4B-8B model keeps a batch this size
# coherent, and a long scene is simply split over several requests.
BATCH_CHARACTERS = 2400
CONTEXT_TURNS = 2
# The lines just before a batch, shown in their original words: a single line is ambiguous
# ("le col" is a mountain pass, a collar or a neck) and the scene around it is what decides.
EARLIER_TURNS = 4
# The context block stays well under the batch itself, so a 4B-8B model still has room.
CONTEXT_CHARACTERS = 3000

SYSTEM = (
    'You are a literary translator for role-play scenes. Translate every entry of the JSON '
    'object you receive from {source} into {target}. Keep the meaning, the register and the '
    'personality of each speaker; render idioms with equivalent idioms rather than word for '
    'word; keep the length close to the original. Text between asterisks is a stage '
    'direction: translate it and keep the asterisks. Tokens written like ⟦1⟧ are voice '
    'directions, not words: copy every one of them unchanged, at the matching place in the '
    'sentence. {names}A context may come first: the world, the place, who speaks and what '
    'was said just before. It is there for understanding only — never translate it and never '
    'copy it into the answer. Use it to choose the sense an ambiguous word has in this place '
    'and at this moment, to keep each speaker\'s register, and to render a name, a place or a '
    'term of this world the same way every time: keep a proper name as it is, and render a '
    'name that has a meaning the way an edition of this world in {target} would. Never add a '
    'note, a comment or an explanation. Answer with the JSON object only, same keys, one '
    'translated string per key.')


def protect(text):
    """The text with its delivery marks replaced by numbered tokens, and the marks."""
    marks = []

    def swap(match):
        marks.append(match.group(0))
        return TOKEN % len(marks)
    return ANNOTATION.sub(swap, text or ''), marks


def restore(text, marks):
    """Put the marks back. Returns the text and the marks the translation lost."""
    seen = set()

    def swap(match):
        index = int(match.group(1))
        if 1 <= index <= len(marks) and index not in seen:
            seen.add(index)
            return marks[index - 1]
        return ''                                   # an invented or repeated token
    restored = TOKEN_PATTERN.sub(swap, text or '')
    restored = restored.replace('⟦', '').replace('⟧', '')
    lost = [marks[index - 1] for index in range(1, len(marks) + 1) if index not in seen]
    return tidy(restored), lost


def translatable(turn):
    """What a stored turn says, without the scene directive that may follow the dialogue."""
    from .scene import split_reply
    content = str(turn.get('content', ''))
    if turn.get('role') == 'assistant':
        return split_reply(content, expect_scene=False)['text']
    return content.strip()


def has_words(text):
    return bool(re.search(r'\w', TOKEN_PATTERN.sub('', text or '')))


def batches(entries, limit=BATCH_CHARACTERS):
    """Split (key, masked text) pairs into requests of bounded size, never splitting a turn."""
    current, size = [], 0
    for key, text in entries:
        if current and size + len(text) > limit:
            yield current
            current, size = [], 0
        current.append((key, text))
        size += len(text)
    if current:
        yield current


def batch_schema(batch):
    """Exactly one non-empty string per key, bounded so a loop cannot run away."""
    return {'type': 'object', 'additionalProperties': False,
            'required': [key for key, _ in batch],
            'properties': {key: {'type': 'string', 'minLength': 1,
                                 'maxLength': min(12000, 200 + 4 * len(text))}
                           for key, text in batch}}


def _clip(value, limit):
    value = ' '.join(str(value or '').split())
    return value if len(value) <= limit else value[:limit - 1].rstrip() + '…'


def _mentioned(entries, focus):
    """Entries whose name appears in the text at hand first: they matter most."""
    folded = (focus or '').casefold()
    return sorted(entries, key=lambda entry: str(entry[0]).casefold() not in folded)


def context_block(world=None, persona=None, session=None, extra='', focus=''):
    """What a translator needs to know and must not translate: the world, its places and
    terms, who speaks and how, and where the scene stands. Bounded; `focus` (the text being
    translated) puts the places and terms it mentions first."""
    lines = []
    if world:
        head = ' — '.join(part for part in (world.get('name'), world.get('genre')) if part)
        if head:
            lines.append('World: ' + _clip(head, 160))
        for label, key, limit in (('Tone', 'tone', 220), ('What it is', 'summary', 380),
                                  ('Where', 'setting', 320)):
            if world.get(key):
                lines.append('%s: %s' % (label, _clip(world[key], limit)))
        places = _mentioned([(item.get('name', ''), item.get('description', ''))
                             for item in world.get('locations') or [] if item.get('name')], focus)
        if places:
            lines.append('Places: ' + '; '.join('%s (%s)' % (name, _clip(text, 90))
                                                 for name, text in places[:8]))
        factions = _mentioned([(item.get('name', ''), item.get('description', ''))
                               for item in world.get('factions') or [] if item.get('name')], focus)
        if factions:
            lines.append('Factions: ' + '; '.join('%s (%s)' % (name, _clip(text, 70))
                                                   for name, text in factions[:6]))
        terms = _mentioned([(item.get('term', ''), item.get('meaning', ''))
                            for item in world.get('glossary') or [] if item.get('term')], focus)
        if terms:
            lines.append('Terms of this world: ' + '; '.join(
                '%s = %s' % (term, _clip(meaning, 80)) for term, meaning in terms[:12]))
    if persona:
        speech = persona.get('speech') or {}
        who = persona.get('name', '')
        summary = (persona.get('personality') or {}).get('summary', '')
        if who:
            lines.append('The character, %s: %s' % (who, _clip(summary, 180)) if summary
                         else 'The character: ' + who)
        manner = '; '.join('%s: %s' % (label, _clip(speech[key], 120)) for label, key in (
            ('style', 'style'), ('register', 'register'), ('vocabulary', 'vocabulary'),
            ('accent', 'accent'), ('tics', 'verbal_tics')) if speech.get(key))
        if manner:
            lines.append('How %s speaks: %s' % (who or 'they', manner))
        state = persona.get('state') or {}
        now = '; '.join('%s: %s' % (label, _clip(state[key], 160)) for label, key in (
            ('situation', 'scenario'), ('place', 'location'), ('time', 'time'),
            ('mood', 'mood')) if state.get(key))
        if now:
            lines.append('The scene now: ' + now)
    if session and session.get('title'):
        lines.append('Scene title: ' + _clip(session['title'], 120))
    if (extra or '').strip():
        lines.append('Note from the person asking for the translation: ' + _clip(extra, 500))
    block = '\n'.join(lines)
    return block if len(block) <= CONTEXT_CHARACTERS else block[:CONTEXT_CHARACTERS - 1] + '…'


def earlier_lines(turns, before, target, count=EARLIER_TURNS, speaker_names=None, produced=None):
    """The `count` turns before index `before`: (speaker, original, translation or '').

    `produced` holds translations made earlier in the same run, by turn index; a stored
    translation in the target language is used otherwise."""
    lines = []
    for index in range(max(0, before - count), before):
        turn = turns[index]
        original = translatable(turn)
        if not has_words(protect(original)[0]):
            continue
        rendered = (produced or {}).get(index) or \
            ((turn.get('translations') or {}).get(target) or {}).get('text', '')
        speaker = (speaker_names or {}).get(turn.get('role'), turn.get('role', ''))
        lines.append((speaker, _clip(original, 400), _clip(rendered, 400)))
    return lines


# ------------------------------------------------------------ the terms of the world
#
# A world's places, factions and glossary terms must read the same in every translation: the
# Roi-Cendre cannot be the Ash King in one scene and the Cinder King in the next. Each term
# is rendered once per language, recorded in the world (term_translations), and required in
# every later request; a translation that drops a required rendering is asked again, and
# what still misses is reported rather than patched.

ARTICLES = ('the ', 'a ', 'an ', 'le ', 'la ', 'les ', "l'", 'un ', 'une ', 'des ', 'el ', 'los ',
            'las ', 'der ', 'die ', 'das ', 'den ', 'dem ', 'il ', 'lo ', 'gli ', 'o ', 'os ', 'as ')


def fold(text):
    import unicodedata
    text = unicodedata.normalize('NFKD', str(text or ''))
    text = ''.join(character for character in text if not unicodedata.combining(character))
    return re.sub(r'\s+', ' ', text.replace('’', "'")).strip().casefold()


def world_terms(world):
    """The name, places, factions and glossary terms of a world: [{'term', 'meaning', 'kind'}].

    The name counts without its subtitle: « Les Archives Flottantes » is said in scenes, « —
    l'Âge des Couronnes Brisées » is not.
    """
    terms, seen = [], set()
    name = str((world or {}).get('name') or '').split(' — ')[0].split(' - ')[0].strip()
    if len(fold(name)) >= 3:
        seen.add(fold(name))
        terms.append({'term': name, 'meaning': _clip((world or {}).get('summary', ''), 160),
                      'kind': 'world'})
    for kind, key, name, meaning in (('term', 'glossary', 'term', 'meaning'),
                                     ('place', 'locations', 'name', 'description'),
                                     ('faction', 'factions', 'name', 'description')):
        for item in (world or {}).get(key) or []:
            term = str(item.get(name) or '').strip()
            if len(fold(term)) < 3 or fold(term) in seen:
                continue
            seen.add(fold(term))
            terms.append({'term': term, 'meaning': _clip(item.get(meaning, ''), 160),
                          'kind': kind})
    return terms


# A leading article is not part of what is looked for: French contracts it with the word
# before (« aux Archives Flottantes », « du Pont des Brumes »), so « Les Archives Flottantes »
# written with its article was never found in a scene.
_LEADING_ARTICLE = re.compile(r"^(?:le|la|les|the|el|los|las|der|die|das|il|lo|gli)\s+|^l'\s*")


def _core_words(term):
    return _LEADING_ARTICLE.sub('', fold(term)).split()


def _term_pattern(term):
    # The term as whole words, a plural s or x allowed at the end: "éclats" is an "Éclat".
    words = [re.escape(word) for word in _core_words(term)] or [re.escape(fold(term))]
    return re.compile(r'(?<![\w])' + r'\s+'.join(words) + r'(?:s|x)?(?![\w])')


def mentioned_terms(terms, text):
    """The terms of the world that a text mentions."""
    folded = fold(text)
    return [item for item in terms if _term_pattern(item['term']).search(folded)]


def used_as_name(term, text):
    """Is the term used as a name of this world here, not as an ordinary word?

    A term of several words or with a hyphen (« Roi-Cendre », « La Brisure ») is a name
    wherever it appears; a single word counts only where it is written with a capital. The
    glossary of Valdrenn holds « Nommer », and « il faut nommer les morts » must stay a verb.
    """
    if re.search(r'[\s\-]', ' '.join(_core_words(term))):
        return True                    # several words or a hyphen: a name wherever it appears
    import unicodedata
    plain = ''.join(c for c in unicodedata.normalize('NFKD', str(text or ''))
                    if not unicodedata.combining(c))
    for match in _term_pattern(term).finditer(fold(plain)):
        if plain[match.start():match.start() + 1].isupper():
            return True
    return False


def _core(rendering):
    """What must be found of a rendering in a translation: without its leading article."""
    core = fold(rendering)
    for article in ARTICLES:
        if core.startswith(article) and len(core) > len(article) + 2:
            return core[len(article):]
    return core


def missed_terms(source, translated, renderings):
    """The required renderings a translation left out, as [term].

    `renderings` maps a term to its rendering; a term the source does not mention is not
    required. A plural or a possessive of the rendering counts ("Shards", "Ash King's").
    """
    folded = fold(translated)
    missed = []
    for term, rendering in renderings.items():
        if not rendering or not _term_pattern(term).search(fold(source)):
            continue
        if not used_as_name(term, source):
            continue                                    # an ordinary word, translated as such
        if _core(rendering) not in folded:
            missed.append(term)
    return missed


def _longest(term):
    """How long a rendering of this term may be: a name, not a sentence about it."""
    return min(80, 2 * len(term) + 24)


def terms_schema(terms):
    return {'type': 'object', 'additionalProperties': False,
            'properties': {item['term']: {'type': 'string', 'minLength': 1,
                                          'maxLength': _longest(item['term'])}
                           for item in terms},
            'required': [item['term'] for item in terms]}


def terms_messages(terms, *, target, source='', world=None):
    """The request that renders new terms once, for every later translation.

    The meaning of each term is given as a hint only. With the meaning presented as part of
    the term, a 4B model translated the hint — « Roi-Cendre » came back as « The lord of the
    Ash Legion. No one has seen his face. »
    """
    system = ('You name things in %s for an edition of the stories of a fictional world. '
              'For each term, answer with its name in %s — a name, never a definition: a few '
              'words at most. Keep an invented proper name as it is. Translate a name made of '
              'real words the way a published edition would, whole — every word of it — with a '
              'leading article in lower case. Answer with the JSON object only.'
              % (target, target))
    lines = []
    if world:
        head = ' — '.join(part for part in (world.get('name'), world.get('genre')) if part)
        if head:
            lines.append('World: ' + _clip(head, 160))
    lines.append('For each term, its name in %s. The hint says what the term is; it is not '
                 'to be translated.' % target)
    for item in terms:
        lines.append('- %s  (a %s; hint: %s)' % (item['term'], item['kind'],
                                                 _clip(item['meaning'], 100) or '—'))
    lines.append('Form of the answer, about another world: {"Vieux-Pont": "Old Bridge", '
                 '"les Freres du Sel": "the Brothers of Salt", "Kerlann": "Kerlann"}')
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': '\n'.join(lines)}]


def lower_article(rendering):
    """« The Shattering » becomes « the Shattering »: a rendering is placed inside sentences,
    and the models asked for it write the article with a capital all the same."""
    for article in ARTICLES:
        if rendering.casefold().startswith(article) and len(rendering) > len(article) + 1 \
                and rendering[:1].isupper():
            return rendering[:len(article)].lower() + rendering[len(article):]
    return rendering


def plausible_rendering(term, rendering):
    """A name, not a description: few words, no sentence punctuation."""
    words = len(rendering.split())
    return bool(rendering) and words <= max(6, 2 * len(term.split()) + 3) \
        and not re.search(r'[.;:!?](\s|$)', rendering)


def parse_terms(answer, terms):
    """{term: rendering} for the renderings that are names; the others are left out, to be
    rendered again next time, and listed in the second value."""
    try:
        document = json.loads(answer)
    except ValueError as exc:
        raise CyToolError('InvalidResponse', 'The terms were not valid JSON: %s' % exc)
    kept, rejected = {}, []
    for item in terms:
        rendering = lower_article(' '.join(str(document.get(item['term'], '')).split()))
        if plausible_rendering(item['term'], rendering):
            kept[item['term']] = rendering
        elif rendering:
            rejected.append(item['term'])
    return kept, rejected


def messages(batch, *, target, source='', names=(), speakers=None, previous=(), context='',
             earlier=(), terms=None, insist=None):
    """The chat request for one batch.

    `context` is the block of context_block(); `earlier` the lines of earlier_lines() — both
    for understanding only. `previous` (translations just made, without their originals) is
    kept for callers that have nothing else."""
    if target not in LANGUAGES:
        raise CyToolError('InvalidParameters', 'Unsupported target language: %s' % target)
    kept = sorted({name.strip() for name in names if name and name.strip()})
    names_line = ('Keep these names exactly as they are written: %s. ' % ', '.join(kept)) \
        if kept else ''
    system = SYSTEM.format(source=source if source and source != 'Auto' else 'its language',
                           target=target, names=names_line)
    request = []
    if context:
        request.append('Context — for understanding only, never translate it:\n' + context)
    if earlier:
        request.append('Just before, in the scene (for understanding only, do not translate '
                       'it again):\n' + '\n'.join(
                           '- %s: %s%s' % (speaker or '?', original,
                                           (' → %s' % rendered) if rendered else '')
                           for speaker, original, rendered in earlier))
    if terms:
        request.append('Names and terms of this world — where one is used as a name or a '
                       'term of this world, render it exactly like this, every time (a plural '
                       'or a possessive may inflect it); an ordinary word that happens to be '
                       'written the same way is translated as usual:\n' + '\n'.join(
                           '- %s → %s' % (term, rendering) for term, rendering in terms.items()))
    if insist:
        request.append('A first attempt did not use these renderings. Use them this time, '
                       'exactly:\n' + '\n'.join('- %s → %s' % (term, rendering)
                                                 for term, rendering in insist.items()))
    if speakers:
        request.append('Who speaks: ' + '; '.join('%s = %s' % (key, speakers[key])
                                                   for key, _ in batch if key in speakers))
    if previous and not earlier:
        request.append('Already translated just before, for continuity only (do not repeat '
                       'it):\n' + '\n'.join('- %s' % line for line in previous))
    request.append('Translate into %s:\n%s' % (target, json.dumps(dict(batch), ensure_ascii=False,
                                                                   indent=1)))
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': '\n\n'.join(request)}]


def parse(answer, batch):
    """The constrained answer as {key: text}; a missing key is an error, not a blank line."""
    try:
        document = json.loads(answer)
    except ValueError as exc:
        raise CyToolError('InvalidResponse', 'The translation was not valid JSON: %s' % exc)
    if not isinstance(document, dict):
        raise CyToolError('InvalidResponse', 'The translation must be a JSON object.')
    missing = [key for key, _ in batch if not str(document.get(key, '')).strip()]
    if missing:
        raise CyToolError('InvalidResponse', 'The translation left out: ' + ', '.join(missing))
    return {key: str(document[key]) for key, _ in batch}
