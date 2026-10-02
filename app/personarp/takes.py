"""Every take of a scene line is kept; one of them is the one the line plays.

A line's `audio` record (on the turn for its own language, on the translation for another)
keeps the shape it always had — file, duration, voice, date — for the chosen take, and lists
every take under `takes`, oldest first. Speaking a line again adds a take and chooses it;
nothing is overwritten. A take can be chosen again, or put in the trash (audio/.trash beside
the scene's takes): nothing is ever deleted.

A record written before takes existed has no list; it counts as a single take.
"""
import shutil
import time
from pathlib import Path

from cytools_core import CyToolError

KEYS = ('file', 'durationSeconds', 'voice', 'at', 'speed', 'pitch')


def holder(turn, language=''):
    """Where the audio of this line, in this language, is recorded."""
    if not language:
        return turn
    translated = (turn.get('translations') or {}).get(language)
    if not translated:
        raise CyToolError('NotFound', 'This line has no %s translation.' % language)
    return translated


def listing(place):
    audio = place.get('audio') or {}
    if audio.get('takes'):
        return [dict(take) for take in audio['takes']]
    return [{key: audio[key] for key in KEYS if key in audio}] if audio.get('file') else []


def chosen(place):
    """The position of the chosen take in the list, or -1."""
    audio = place.get('audio') or {}
    for position, take in enumerate(listing(place)):
        if take.get('file') == audio.get('file'):
            return position
    return -1


def _record(everything, position):
    return {**{key: value for key, value in everything[position].items() if key in KEYS},
            'takes': everything}


def add(place, take):
    """A new take, which becomes the one the line plays."""
    everything = listing(place) + [{key: take[key] for key in KEYS if key in take}]
    place['audio'] = _record(everything, len(everything) - 1)
    return place['audio']


def choose(place, position):
    everything = listing(place)
    if not 0 <= position < len(everything):
        raise CyToolError('InvalidParameters', 'This line has no take %d.' % (position + 1))
    place['audio'] = _record(everything, position)
    return place['audio']


def remove(place, position, trash):
    """Put one take in the trash; the line then plays the latest take left, if any."""
    everything = listing(place)
    if not 0 <= position < len(everything):
        raise CyToolError('InvalidParameters', 'This line has no take %d.' % (position + 1))
    was_chosen = chosen(place) == position
    gone = everything.pop(position)
    moved = ''
    source = Path(gone.get('file', ''))
    if source.is_file():
        trash.mkdir(parents=True, exist_ok=True)
        target = trash / (source.stem + '-' + time.strftime('%Y%m%d-%H%M%S') + source.suffix)
        shutil.move(str(source), str(target))
        moved = str(target)
    if not everything:
        place.pop('audio', None)
    else:
        keep = len(everything) - 1 if was_chosen else chosen({'audio': {
            **place['audio'], 'takes': everything}})
        place['audio'] = _record(everything, max(keep, 0))
    return {'trash': moved, 'left': len(everything)}


def retire(place, trash):
    """The words changed: every take of the old words goes to the trash."""
    moved = []
    for take in listing(place):
        source = Path(take.get('file', ''))
        if source.is_file():
            trash.mkdir(parents=True, exist_ok=True)
            target = trash / (source.stem + '-' + time.strftime('%Y%m%d-%H%M%S') + source.suffix)
            shutil.move(str(source), str(target))
            moved.append(str(target))
    place.pop('audio', None)
    return moved


def file_for(folder, index, language):
    """A new file name for a take of this line: never the name of an earlier take."""
    stem = 'turn-%03d-%s-%s' % (index, (language or 'original').lower(), time.strftime('%Y%m%d-%H%M%S'))
    target, number = folder / (stem + '.wav'), 2
    while target.exists():
        target = folder / ('%s-%d.wav' % (stem, number))
        number += 1
    return target
