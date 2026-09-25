"""Turning a character's inline delivery marks into a speech plan.

`scene.parse_annotations` already recognises the vocabulary the character writes —
[ton: sourd], [emotion: soulagement], [pause: 400ms], [rate: lent], [volume: murmure],
[emphasis: jamais], [rire] — in French and English. This module compiles that into an
ordered plan of passages and exact silences:

    {'text': ..., 'instruction': ..., 'direction': ...}   a passage to speak
    {'pauseSeconds': 0.4}                                 exact silence

A direction is persistent: it applies from where it appears until it is reset or replaced,
which is how a character keeps a tone for a whole paragraph without annotating every
sentence. [emphasis: ...] is the exception — it applies to the passage it opens only.

Tags never reach the spoken text. This is orchestration on our side, not native markup in
any model: a backend that cannot follow a direction simply speaks the words.
"""
import re

from ..marks import ANNOTATION, BARE_VALUES, DURATION, KINDS

MAX_SEGMENTS = 128
MAX_PAUSE_SECONDS = 10.0
MAX_TOTAL_PAUSE_SECONDS = 60.0
RESET_WORDS = ('reset', 'normal', 'default', 'neutre', 'neutral', 'fin', 'end')

# How each canonical kind reads in the instruction handed to the model.
PHRASING = {
    'tone': 'tone: %s',
    'emotion': 'emotion: %s',
    'rate': 'pace: %s',
    'volume': 'loudness: %s',
    'sound': 'audible %s at this point',
    'emphasis': 'stress the words "%s"',
}
ONE_SHOT = ('emphasis', 'sound')


class AnnotationError(ValueError):
    pass


def _seconds(value):
    match = DURATION.match(value or '')
    if not match:
        raise AnnotationError('Use [pause: 500ms] or [pause: 1s].')
    amount = float(match.group(1).replace(',', '.'))
    unit = (match.group(2) or 'ms').lower()
    return amount / 1000 if unit == 'ms' else amount


def split_delivery(text, delivery):
    """How much is sent to the backend at a time; shorter pieces start playing sooner."""
    if delivery == 'segments':
        parts = re.split(r'(?<=[.!?;])\s+|\n+', text)
    elif delivery == 'paragraphs':
        parts = re.split(r'\r?\n[ \t]*\r?\n+', text)
    else:
        parts = [text]
    return [part.strip() for part in parts if part and part.strip()]


def build_plan(text, *, enabled=True, delivery='paragraphs', base_instruction=''):
    plan = []
    persistent = {}
    pending = {}
    cursor = 0
    pause_total = 0.0

    def instruction_for(directions):
        parts = [base_instruction] if base_instruction else []
        phrases = [PHRASING.get(kind, '%s') % value for kind, value in directions.items() if value]
        if phrases:
            parts.append('For this passage, deliver it with — ' + '; '.join(phrases)
                         + '. This overrides any conflicting direction above.')
        return '\n'.join(parts)

    def speech(value):
        nonlocal pending
        # A one-shot mark belongs to the passage it opens. With a fine delivery one call can
        # yield several passages, so it is consumed by the first of them, not by all.
        for part in split_delivery(value, delivery):
            directions = {**persistent, **pending}
            pending = {}
            plan.append({'text': part, 'instruction': instruction_for(directions),
                         'direction': '; '.join('%s=%s' % item for item in directions.items())})

    if not enabled:
        speech(text)
    else:
        for match in ANNOTATION.finditer(text or ''):
            name = (match.group(1) or '').strip().lower()
            kind = KINDS.get(name)
            if kind is None:
                continue                      # ordinary square brackets stay in the text
            if match.start() < cursor:
                continue
            speech(text[cursor:match.start()])
            cursor = match.end()
            value = (match.group(2) or '').strip() or BARE_VALUES.get(name, name)
            if kind == 'pause':
                seconds = _seconds(value)
                pause_total += seconds
                if seconds > MAX_PAUSE_SECONDS or pause_total > MAX_TOTAL_PAUSE_SECONDS:
                    raise AnnotationError('Pauses: at most 10 seconds each and 60 seconds in total.')
                if seconds:
                    plan.append({'pauseSeconds': seconds})
                continue
            if len(value) > 256 or '[' in value:
                raise AnnotationError('A delivery annotation holds 1 to 256 characters.')
            if value.lower() in RESET_WORDS:
                persistent.pop(kind, None)
            elif kind in ONE_SHOT:
                pending[kind] = value
            else:
                persistent[kind] = value
        speech(text[cursor:])

    if not any('text' in item for item in plan):
        raise AnnotationError('There is text to speak, not only annotations.')
    if len(plan) > MAX_SEGMENTS:
        raise AnnotationError('At most %d passages and pauses per take.' % MAX_SEGMENTS)
    return plan


def render_plan(plan, synthesize, emit):
    """Keep one engine loaded, insert exact silence, preserve order.

    synthesize(item) -> (audio float32 1-D, samplerate); emit(audio, rate, item).
    Returns the sample rate used.
    """
    import numpy as np
    rate = None
    waiting = []
    for item in plan:
        if 'pauseSeconds' in item:
            if rate is None:
                waiting.append(item)          # a leading pause needs a rate we do not have yet
            else:
                emit(np.zeros(round(item['pauseSeconds'] * rate), dtype=np.float32), rate, item)
            continue
        wave, current = synthesize(item)
        audio = np.asarray(wave, dtype=np.float32)
        if audio.ndim == 2:
            audio = audio[0] if audio.shape[0] <= 2 else audio[:, 0]
        if audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
            raise RuntimeError('The model returned invalid audio.')
        if rate is not None and rate != current:
            raise RuntimeError('The sample rate changed between passages.')
        rate = current
        for pause in waiting:
            emit(np.zeros(round(pause['pauseSeconds'] * rate), dtype=np.float32), rate, pause)
        waiting.clear()
        emit(audio, rate, item)
    return rate
