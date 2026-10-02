"""The sheet's speed and pitch, applied to a take once the model has spoken it.

Qwen3-TTS has no rate or pitch control, so both are signal processing on the result:

- speed changes the duration without changing the pitch: WSOLA (waveform-similarity
  overlap-add), which keeps speech free of the phasing a plain phase vocoder adds;
- pitch, in semitones, is a time stretch by the pitch ratio followed by resampling back,
  so the duration is untouched. Formants move with it: a few semitones change the voice's
  height, a full octave turns it into another voice.

Both are done in one stretch and one resampling. Only the lines delivered to the user are
processed; the takes a stable voice is captured from never are, or every clone would
inherit the change once more. numpy only, so it runs in the window, the CLI, MCP and Colab.
"""
import numpy as np
import soundfile as sf

NEUTRAL_SPEED = 1.0
NEUTRAL_PITCH = 0.0
FRAME_SECONDS = 0.030
TOLERANCE_SECONDS = 0.010


def settings(voice):
    """(speed, pitch) from a sheet's voice, clamped to what the schema allows."""
    voice = voice or {}
    speed = float(voice.get('speed', NEUTRAL_SPEED) or NEUTRAL_SPEED)
    pitch = float(voice.get('pitch', NEUTRAL_PITCH) or NEUTRAL_PITCH)
    return min(4.0, max(0.25, speed)), min(12.0, max(-12.0, pitch))


def neutral(speed, pitch):
    return abs(speed - NEUTRAL_SPEED) < 1e-3 and abs(pitch - NEUTRAL_PITCH) < 1e-3


def stretch(audio, factor, rate):
    """WSOLA: the result lasts len(audio) * factor samples, at the same pitch."""
    audio = np.asarray(audio, dtype=np.float64)
    if abs(factor - 1.0) < 1e-4 or len(audio) == 0:
        return audio.copy()
    frame = max(64, int(FRAME_SECONDS * rate) // 2 * 2)
    hop = frame // 2
    tolerance = max(1, int(TOLERANCE_SECONDS * rate))
    window = np.hanning(frame)
    length = int(round(len(audio) * factor))
    padded = np.pad(audio, (tolerance, frame + hop + 2 * tolerance))
    output = np.zeros(length + frame)
    weight = np.zeros(length + frame)
    previous = None
    for position in range(0, length, hop):
        ideal = int(position / factor)
        if previous is None:
            chosen = ideal
        else:
            # The frame that best continues what was just written: the natural sequel of
            # the previous frame, searched for around where the stretch says we should be.
            follow = padded[previous + hop + tolerance: previous + hop + tolerance + frame]
            region = padded[ideal: ideal + frame + 2 * tolerance]
            if len(follow) < frame or len(region) < frame + 2 * tolerance:
                chosen = ideal
            else:
                score = np.correlate(region, follow, mode='valid')
                chosen = ideal + int(np.argmax(score)) - tolerance
        chosen = max(-tolerance, chosen)
        piece = padded[chosen + tolerance: chosen + tolerance + frame]
        if len(piece) < frame:
            piece = np.pad(piece, (0, frame - len(piece)))
        output[position: position + frame] += piece * window
        weight[position: position + frame] += window
        previous = chosen
    covered = weight > 1e-3
    output[covered] /= weight[covered]
    return output[:length]


def resample(audio, length):
    """Band-limited resampling to `length` samples (FFT, no aliasing when shortening)."""
    audio = np.asarray(audio, dtype=np.float64)
    if length == len(audio) or len(audio) == 0:
        return audio.copy()
    spectrum = np.fft.rfft(audio)
    bins = length // 2 + 1
    if bins <= len(spectrum):
        spectrum = spectrum[:bins]
    else:
        spectrum = np.pad(spectrum, (0, bins - len(spectrum)))
    return np.fft.irfft(spectrum, n=length) * (length / len(audio))


def transform(audio, rate, speed=NEUTRAL_SPEED, pitch=NEUTRAL_PITCH):
    """The audio spoken `speed` times faster and `pitch` semitones higher."""
    audio = np.asarray(audio)
    if neutral(speed, pitch) or len(audio) == 0:
        return audio
    ratio = 2.0 ** (pitch / 12.0)
    target = max(1, int(round(len(audio) / speed)))
    stretched = stretch(audio, ratio / speed, rate)
    shaped = resample(stretched, target)
    peak = float(np.max(np.abs(shaped))) if len(shaped) else 0.0
    if peak > 0.999:                          # resampling can overshoot; never clip
        shaped = shaped * (0.999 / peak)
    return shaped.astype(np.float32)


def apply_to_file(path, speed, pitch):
    """Rewrite one WAV in place. Returns its new sample count."""
    audio, rate = sf.read(str(path), dtype='float32', always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    shaped = transform(audio, rate, speed, pitch)
    sf.write(str(path), shaped, rate, subtype='PCM_16')
    return len(shaped), rate


def apply_to_take(result, speed, pitch):
    """A take from the worker: each passage, then the whole line rebuilt from them.

    The timeline keeps pointing at the right samples, so highlighting a passage while it is
    heard still works.
    """
    if neutral(speed, pitch) or not result.get('file'):
        return result
    segments = [segment for segment in result.get('segments') or [] if segment.get('file')]
    if not segments:
        count, rate = apply_to_file(result['file'], speed, pitch)
        return {**result, 'durationSeconds': count / rate, 'speed': speed, 'pitch': pitch}
    pieces, offset, rate = [], 0, result.get('sampleRate') or 24000
    timeline = []
    for segment in segments:
        count, rate = apply_to_file(segment['file'], speed, pitch)
        audio, _ = sf.read(segment['file'], dtype='float32', always_2d=False)
        pieces.append(audio)
        timeline.append({**segment, 'startSample': offset, 'sampleCount': count})
        offset += count
    whole = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
    sf.write(str(result['file']), whole, rate, subtype='PCM_16')
    return {**result, 'segments': timeline, 'durationSeconds': len(whole) / rate,
            'speed': speed, 'pitch': pitch}
