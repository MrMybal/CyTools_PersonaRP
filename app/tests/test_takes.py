"""Every take of a line is kept, and the sheet's speed and pitch shape what is delivered.

No model: the speech worker is replaced by one that writes a real tone, so durations and the
fundamental frequency can be measured on what the Tool stores.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import tool                                                                 # noqa: E402
from personarp import library, locks, sessions, takes                       # noqa: E402
from personarp.schemas import FORMAT_PERSONA, normalize_persona, normalize_world  # noqa: E402
from personarp.voice import delivery, prosody, stable                       # noqa: E402

RATE = 24000


def _tone(path, seconds=2.0, frequency=220.0):
    t = np.arange(int(seconds * RATE)) / RATE
    sf.write(str(path), (0.4 * np.sin(2 * np.pi * frequency * t)).astype(np.float32), RATE,
             subtype='PCM_16')
    return path


def _fundamental(audio):
    middle = audio[len(audio) // 4: len(audio) // 4 + RATE // 2]
    middle = middle - middle.mean()
    corr = np.correlate(middle, middle, mode='full')[len(middle) - 1:]
    lag = 40 + int(np.argmax(corr[40:400]))
    return RATE / lag


def _seconds(path):
    info = sf.info(str(path))
    return info.frames / info.samplerate


class FakeSpeech:
    """Writes two passages of tone, as the worker does: segments and the whole line."""

    def __init__(self):
        self.calls = 0

    def __call__(self, context, payload, offset=0.0, scale=1.0):
        self.calls += 1
        out = Path(payload['workspace']) / payload['output_dir']
        out.mkdir(parents=True, exist_ok=True)
        first = _tone(out / 'segment-0001.wav', 1.2)
        second = _tone(out / 'segment-0002.wav', 0.8)
        whole = np.concatenate([sf.read(str(first))[0], sf.read(str(second))[0]])
        sf.write(str(out / 'speech.wav'), whole, RATE, subtype='PCM_16')
        return {'file': str(out / 'speech.wav'), 'sampleRate': RATE, 'durationSeconds': 2.0,
                'segments': [{'text': 'a', 'startSample': 0, 'sampleCount': int(1.2 * RATE),
                              'file': str(first)},
                             {'text': 'b', 'startSample': int(1.2 * RATE),
                              'sampleCount': int(0.8 * RATE), 'file': str(second)}],
                'mode': payload['mode'], 'model': payload['model']}


@pytest.fixture()
def scene(tmp_path, monkeypatch):
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(sessions, 'SESSIONS', tmp_path / 'sessions')
    monkeypatch.setattr(locks, 'SETTINGS', tmp_path / 'settings')
    voices = tmp_path / 'voices'
    voices.mkdir()
    monkeypatch.setattr(stable, 'VOICES', voices)
    monkeypatch.setattr(library, 'VOICES', voices)
    models = {'custom': {'backend': 'qwen3tts', 'variant': '1.7B-CustomVoice'},
              'design': {'backend': 'qwen3tts', 'variant': '1.7B-VoiceDesign'},
              'base': {'backend': 'qwen3tts', 'variant': '1.7B-Base'}}
    monkeypatch.setattr(delivery.catalog, 'catalog', lambda: models)
    monkeypatch.setattr(delivery.catalog, 'installed', lambda key: True)
    monkeypatch.setattr(delivery.catalog, 'directory', lambda key: Path('/models') / key)
    speech = FakeSpeech()
    monkeypatch.setattr(tool.voice_runner, 'speak', speech)
    persona = personas.create({'name': 'Wren', 'voice': {'language': 'French', 'speaker': 'Ryan'}})
    session = sessions.create(persona['id'], 'Test')
    sessions.append_turn(session, 'user', 'Salut.')
    sessions.append_turn(session, 'assistant', 'Ouais bon. Salut à toi aussi.')
    sessions.save(session)
    return {'persona': persona, 'session': session, 'speech': speech, 'personas': personas}


def _run(runtime, operation, parameters):
    actor = runtime.authenticate(runtime.create_client('Test', [])['token'])
    session = runtime.create_session(actor, temporary=True)['sessionId']
    job = runtime.submit(actor, session, operation, parameters)
    return runtime.wait(actor, job['jobId'], timeout=60)


def _line(scene):
    return {'persona_id': scene['persona']['id'], 'session_id': scene['session']['id'], 'turn': 1}


def _stored_turn(scene):
    return sessions.get(scene['persona']['id'], scene['session']['id'])['turns'][1]


# ------------------------------------------------------------------------ takes

def test_speaking_a_line_again_keeps_the_earlier_take(scene):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        first = _run(runtime, 'speak_turn', _line(scene))
        second = _run(runtime, 'speak_turn', _line(scene))
    assert first['state'] == second['state'] == 'Completed', (first.get('error'), second.get('error'))
    audio = _stored_turn(scene)['audio']
    assert [take['file'] for take in audio['takes']] == [first['outputs']['file'],
                                                         second['outputs']['file']]
    assert first['outputs']['file'] != second['outputs']['file']
    assert all(Path(take['file']).is_file() for take in audio['takes'])
    assert audio['file'] == second['outputs']['file']                  # the newest plays


def test_an_earlier_take_can_be_chosen_again(scene):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        first = _run(runtime, 'speak_turn', _line(scene))['outputs']['file']
        _run(runtime, 'speak_turn', _line(scene))
        chosen = _run(runtime, 'choose_take', {**_line(scene), 'take': 0})
        wrong = _run(runtime, 'choose_take', {**_line(scene), 'take': 5})
    assert chosen['state'] == 'Completed', chosen.get('error')
    assert chosen['outputs']['chosen'] == 0 and chosen['outputs']['audio']['file'] == first
    assert _stored_turn(scene)['audio']['file'] == first
    assert len(_stored_turn(scene)['audio']['takes']) == 2
    assert wrong['state'] == 'Failed' and 'no take 6' in wrong['error']['message']


def test_a_take_goes_to_the_trash_and_the_line_plays_the_one_left(scene):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        first = _run(runtime, 'speak_turn', _line(scene))['outputs']['file']
        second = _run(runtime, 'speak_turn', _line(scene))['outputs']['file']
        removed = _run(runtime, 'remove_take', {**_line(scene), 'take': 1})
        assert removed['state'] == 'Completed', removed.get('error')
        assert not Path(second).exists() and Path(removed['outputs']['trash']).is_file()
        assert Path(removed['outputs']['trash']).parent.name == '.trash'
        assert _stored_turn(scene)['audio']['file'] == first
        last = _run(runtime, 'remove_take', {**_line(scene), 'take': 0})
    assert last['outputs']['left'] == 0 and 'audio' not in _stored_turn(scene)
    assert Path(last['outputs']['trash']).is_file()                    # moved, not deleted


def test_a_take_recorded_before_takes_existed_counts_as_one(scene):
    session = sessions.get(scene['persona']['id'], scene['session']['id'])
    old = _tone(Path(tempfile.mkdtemp()) / 'turn-001-original.wav')
    session['turns'][1]['audio'] = {'file': str(old), 'durationSeconds': 2.0, 'at': 'earlier'}
    sessions.save(session)
    assert len(takes.listing(_stored_turn(scene))) == 1
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        _run(runtime, 'speak_turn', _line(scene))
    audio = _stored_turn(scene)['audio']
    assert [take['file'] for take in audio['takes']][0] == str(old) and len(audio['takes']) == 2


# ------------------------------------------------------------------ speed and pitch

def test_the_transform_keeps_what_it_promises():
    t = np.arange(2 * RATE) / RATE
    tone = 0.4 * np.sin(2 * np.pi * 220 * t)
    assert prosody.transform(tone, RATE) is tone or np.array_equal(prosody.transform(tone, RATE), tone)
    faster = prosody.transform(tone, RATE, speed=1.5)
    assert abs(len(faster) / RATE - 2.0 / 1.5) < 0.01 and abs(_fundamental(faster) - 220) < 4
    higher = prosody.transform(tone, RATE, pitch=12.0)
    assert abs(len(higher) / RATE - 2.0) < 0.01 and abs(_fundamental(higher) - 440) < 8
    lower = prosody.transform(tone, RATE, speed=0.8, pitch=-5.0)
    assert abs(len(lower) / RATE - 2.5) < 0.01 and abs(_fundamental(lower) - 164.8) < 4
    assert float(np.max(np.abs(higher))) <= 0.999


def test_a_line_is_delivered_at_the_sheet_speed_and_pitch(scene):
    sheet = scene['personas'].get(scene['persona']['id'])
    sheet['voice'].update(speed=1.25, pitch=12.0)
    scene['personas'].save(sheet)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_turn', _line(scene))
    assert result['state'] == 'Completed', result.get('error')
    kept = result['outputs']['file']
    audio, _ = sf.read(kept)
    assert abs(_seconds(kept) - 2.0 / 1.25) < 0.02
    assert abs(result['outputs']['durationSeconds'] - 1.6) < 0.02
    assert abs(_fundamental(audio) - 440) < 8
    segments = result['outputs']['segments']
    assert sum(segment['sampleCount'] for segment in segments) == sf.info(kept).frames
    assert segments[1]['startSample'] == segments[0]['sampleCount']
    record = _stored_turn(scene)['audio']
    assert record['speed'] == 1.25 and record['pitch'] == 12.0


def test_the_take_a_voice_is_captured_from_is_never_shaped(scene, monkeypatch):
    sheet = scene['personas'].get(scene['persona']['id'])
    sheet['voice'].update(speed=2.0, pitch=-7.0, description='Une voix grave.')
    scene['personas'].save(sheet)
    shaped = []
    monkeypatch.setattr(prosody, 'apply_to_take', lambda result, *a: shaped.append(a) or result)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        captured = _run(runtime, 'capture_voice_take', {'persona_id': sheet['id']})
        spoken = _run(runtime, 'speak_turn', _line(scene))
    assert captured['state'] == 'Completed', captured.get('error')
    assert abs(captured['outputs']['durationSeconds'] - 2.0) < 0.01
    assert spoken['state'] == 'Completed' and shaped == [(2.0, -7.0)]   # only the scene line
