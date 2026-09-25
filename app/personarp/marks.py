"""The delivery-mark vocabulary, with no dependencies at all.

Both sides need it and they do not share an environment: `scene.py` runs in the Tool's own
runtime next to CyToolsCore, while the speech worker runs inside the private voice engine
where the SDK is not installed. Keeping the grammar here, on the standard library alone,
is what lets the character's annotations mean the same thing in both places.
"""
import re

# [key] or [key: value]; the value stops at the closing bracket.
ANNOTATION = re.compile(r'\[([A-Za-zÀ-ÿ_][A-Za-zÀ-ÿ0-9_ -]{0,24})(?:[:=]\s*([^\]\[]{0,120}))?\]')

# French and English spellings map to one canonical kind, so a sheet written in either
# language drives the same backend parameter.
KINDS = {
    'tone': 'tone', 'ton': 'tone', 'tonalite': 'tone', 'tonalité': 'tone',
    'emotion': 'emotion', 'émotion': 'emotion', 'humeur': 'emotion', 'mood': 'emotion',
    'pause': 'pause', 'silence': 'pause', 'beat': 'pause',
    'rate': 'rate', 'rythme': 'rate', 'debit': 'rate', 'débit': 'rate', 'speed': 'rate',
    'volume': 'volume', 'intensite': 'volume', 'intensité': 'volume',
    'emphasis': 'emphasis', 'emphase': 'emphasis', 'accent': 'emphasis',
    'whisper': 'volume', 'chuchote': 'volume', 'murmure': 'volume',
    'shout': 'volume', 'crie': 'volume',
    'laugh': 'sound', 'rire': 'sound', 'soupir': 'sound', 'sigh': 'sound',
    'breath': 'sound', 'souffle': 'sound',
}

# A bare [murmure] carries its own value; [ton: ...] needs one.
BARE_VALUES = {'whisper': 'whisper', 'chuchote': 'whisper', 'murmure': 'whisper',
               'shout': 'shout', 'crie': 'shout', 'laugh': 'laugh', 'rire': 'laugh',
               'soupir': 'sigh', 'sigh': 'sigh', 'breath': 'breath', 'souffle': 'breath'}

NARRATION = re.compile(r'\*[^*]{1,600}\*')
DURATION = re.compile(r'^\s*(\d{1,5}(?:[.,]\d+)?)\s*(ms|s|sec|secondes?|seconds?)?\s*$',
                      re.IGNORECASE)


def duration_ms(value):
    """Milliseconds for a [pause: …] value, or None when it is not a duration."""
    match = DURATION.match(value or '')
    if not match:
        return None
    amount = float(match.group(1).replace(',', '.'))
    unit = (match.group(2) or 'ms').lower()
    return amount if unit == 'ms' else amount * 1000


def tidy(text):
    """Close the gaps a removed mark leaves behind.

    "Bonjour [tone: doux]." would otherwise become "Bonjour ." — which a reader notices and
    a speech backend turns into an audible pause.
    """
    value = re.sub(r'[ \t]+', ' ', text or '')
    value = re.sub(r'[ \t]+([,.;:!?…»)\]])', r'\1', value)
    value = re.sub(r'([(\[«])[ \t]+', r'\1', value)
    value = re.sub(r'[ \t]+\n', '\n', value)
    return value.strip()
