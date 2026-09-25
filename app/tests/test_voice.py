"""Voice tests that need no model: the speech plan, stable voices, variant selection.

Real synthesis is covered by app/tests/acceptance_voice.py, which loads weights.
"""
import struct
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cytools_core import CyToolError                                        # noqa: E402

from personarp.schemas import normalize_persona                             # noqa: E402
from personarp.voice import delivery, stable                                # noqa: E402
from personarp.voice.annotations import (AnnotationError, build_plan,       # noqa: E402
                                         render_plan, split_delivery)


# ------------------------------------------------------------------- speech plan

def _texts(plan):
    return [item['text'] for item in plan if 'text' in item]


def _pauses(plan):
    return [item['pauseSeconds'] for item in plan if 'pauseSeconds' in item]


def test_plain_text_is_one_passage():
    plan = build_plan('Bonjour toi.', delivery='complete')
    assert _texts(plan) == ['Bonjour toi.'] and _pauses(plan) == []


def test_a_tone_persists_until_it_is_reset():
    plan = build_plan('[ton: sourd] Un. Deux. [ton: normal] Trois.', delivery='segments')
    directions = {item['text']: item['direction'] for item in plan if 'text' in item}
    assert 'tone=sourd' in directions['Un.']
    assert 'tone=sourd' in directions['Deux.']
    assert directions['Trois.'] == ''


def test_emphasis_applies_to_one_passage_only():
    plan = build_plan('[emphasis: jamais] Un. Deux.', delivery='segments')
    directions = [item['direction'] for item in plan if 'text' in item]
    assert 'emphasis=jamais' in directions[0]
    assert 'emphasis' not in directions[1]


def test_pause_becomes_a_real_silence_item():
    plan = build_plan('Un. [pause: 400ms] Deux.', delivery='complete')
    assert _pauses(plan) == [0.4]
    assert _texts(plan) == ['Un.', 'Deux.']


def test_seconds_and_milliseconds_are_both_accepted():
    assert _pauses(build_plan('a [pause: 1s] b')) == [1.0]
    assert _pauses(build_plan('a [pause: 250ms] b')) == [0.25]


def test_a_bare_mark_carries_its_own_value():
    plan = build_plan('[murmure] Approche.', delivery='complete')
    assert 'volume=whisper' in plan[0]['direction']


def test_annotations_never_reach_the_spoken_text():
    plan = build_plan('[ton: bas] Bonjour [pause: 200ms] toi.', delivery='complete')
    for item in plan:
        assert '[' not in item.get('text', '')


def test_unknown_brackets_stay_in_the_text():
    plan = build_plan('Il lit [note de bas de page] et continue.', delivery='complete')
    assert '[note de bas de page]' in plan[0]['text']


def test_an_absurd_pause_is_refused():
    with pytest.raises(AnnotationError):
        build_plan('a [pause: 30s] b')


def test_only_annotations_is_refused():
    with pytest.raises(AnnotationError):
        build_plan('[ton: bas] [pause: 200ms]')


def test_a_malformed_pause_is_refused():
    with pytest.raises(AnnotationError):
        build_plan('a [pause: bientot] b')


def test_instruction_carries_the_direction_and_the_standing_one():
    plan = build_plan('[emotion: soulagement] Enfin.', base_instruction='Une archiviste calme.')
    instruction = plan[0]['instruction']
    assert 'Une archiviste calme.' in instruction
    assert 'emotion: soulagement' in instruction


def test_split_delivery_modes():
    text = 'Un. Deux.\n\nTrois.'
    assert len(split_delivery(text, 'complete')) == 1
    assert len(split_delivery(text, 'paragraphs')) == 2
    assert len(split_delivery(text, 'segments')) == 3


def test_render_plan_inserts_silence_at_the_right_rate():
    import numpy as np
    plan = build_plan('Un. [pause: 500ms] Deux.', delivery='complete')
    produced = []

    def synthesize(item):
        return np.ones(1000, dtype=np.float32), 24000

    def emit(audio, rate, item):
        produced.append((len(audio), rate, 'pauseSeconds' in item))

    rate = render_plan(plan, synthesize, emit)
    assert rate == 24000
    assert produced[1] == (12000, 24000, True)          # 0.5 s of silence at 24 kHz
    assert [p[2] for p in produced] == [False, True, False]


def test_a_leading_pause_plays_before_the_speech():
    """Its length is only known once a passage has revealed the sample rate, but it must
    still come out first."""
    import numpy as np
    plan = build_plan('[pause: 250ms] Un.', delivery='complete')
    produced = []
    render_plan(plan, lambda item: (np.ones(10, dtype=np.float32), 16000),
                lambda audio, rate, item: produced.append((len(audio), 'pauseSeconds' in item)))
    assert produced == [(4000, True), (10, False)]


# ------------------------------------------------------------- variant selection

def test_each_mode_maps_to_the_weights_that_can_do_it():
    assert delivery.VARIANTS['clone'][0] == '1.7B-Base'
    assert delivery.VARIANTS['custom'][0] == '1.7B-CustomVoice'
    assert delivery.VARIANTS['design'][0] == '1.7B-VoiceDesign'
    # No variant may claim two modes: that is the mistake this table exists to prevent.
    for mode, variants in delivery.VARIANTS.items():
        for other, others in delivery.VARIANTS.items():
            if other != mode:
                assert not set(variants) & set(others), (mode, other)


def test_model_for_reports_which_variant_is_missing(monkeypatch):
    monkeypatch.setattr(delivery.catalog, 'catalog', lambda: {})
    with pytest.raises(CyToolError) as failure:
        delivery._model_for('clone', '')
    assert '1.7B-Base' in str(failure.value)


def test_model_for_substitutes_and_says_so(monkeypatch):
    models = {'a': {'backend': 'qwen3tts', 'variant': '0.6B-Base'}}
    monkeypatch.setattr(delivery.catalog, 'catalog', lambda: models)
    monkeypatch.setattr(delivery.catalog, 'installed', lambda key: True)
    monkeypatch.setattr(delivery.catalog, 'directory', lambda key: Path('/models') / key)
    entry, note = delivery._model_for('clone', '1.7B-CustomVoice')
    assert entry['id'] == 'a'
    assert 'cannot clone' in note


# --------------------------------------------------------------- persona payload

def _persona(**voice):
    return normalize_persona({
        'name': 'Nymphaea',
        'personality': {'summary': 'vive'},
        'speech': {'style': 'phrases courtes'},
        'state': {'mood': 'curieuse', 'location': 'Le Pont'},
        'background': {'secrets': 'un livre cache'},
        'memory': {'facts': ['un fait secret']},
        'voice': voice})


def test_the_instruction_uses_the_sheet_but_not_the_lore():
    instruction = delivery.persona_instruction(_persona(use_persona_style=True), None, 'Salut')
    assert 'Nymphaea' in instruction and 'phrases courtes' in instruction
    assert 'curieuse' in instruction
    assert 'un livre cache' not in instruction and 'un fait secret' not in instruction


def test_persona_style_can_be_turned_off():
    instruction = delivery.persona_instruction(
        _persona(use_persona_style=False, instruction='Voix grave.'), None, '')
    assert 'Voix grave.' in instruction and 'Nymphaea' not in instruction


def test_the_instruction_stays_bounded():
    persona = _persona(use_persona_style=True, instruction='x' * 2000)
    assert len(delivery.persona_instruction(persona, None, 'y' * 4000)) <= delivery.MAX_INSTRUCTION


def test_a_missing_stable_voice_degrades_with_an_explanation(monkeypatch):
    monkeypatch.setattr(stable, 'exists', lambda identifier: False)
    document, note = delivery.resolve_voice(_persona(voice_id='absent'))
    assert document is None and 'not in the library' in note


# --------------------------------------------------------------- stable voices

def _wav(path, seconds, rate=24000):
    frames = int(seconds * rate)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack('<%dh' % frames, *([0] * frames)))
    return path


@pytest.fixture()
def voices(tmp_path, monkeypatch):
    folder = tmp_path / 'voices'
    folder.mkdir()
    monkeypatch.setattr(stable, 'VOICES', folder)
    return folder


def test_create_registers_and_locks_a_voice(voices, tmp_path):
    take = _wav(tmp_path / 'take.wav', 18.0)
    document = stable.create('Nymphaea', take, 'Bonjour, voici ma voix.')
    assert document['locked'] is True
    assert 17.9 < document['reference_seconds'] < 18.1
    assert Path(document['reference_audio']).parent == voices
    assert document['reference_sha256']
    assert stable.verify(document['id'])['ok']


def test_a_reference_without_its_words_is_refused(voices, tmp_path):
    take = _wav(tmp_path / 'take.wav', 18.0)
    with pytest.raises(CyToolError) as failure:
        stable.create('Nymphaea', take, '   ')
    assert 'exact words' in str(failure.value)


def test_a_reference_that_is_far_too_short_is_refused(voices, tmp_path):
    take = _wav(tmp_path / 'blip.wav', 1.0)
    with pytest.raises(CyToolError):
        stable.create('Nymphaea', take, 'Bonjour.')


def test_a_changed_reference_is_detected(voices, tmp_path):
    take = _wav(tmp_path / 'take.wav', 15.0)
    document = stable.create('Nymphaea', take, 'Bonjour.')
    _wav(Path(document['reference_audio']), 9.0)          # someone replaced the recording
    result = stable.verify(document['id'])
    assert not result['ok'] and 'changed' in result['reason']


def test_a_missing_reference_is_detected(voices, tmp_path):
    document = stable.create('Nymphaea', _wav(tmp_path / 'take.wav', 15.0), 'Bonjour.')
    Path(document['reference_audio']).unlink()
    assert not stable.verify(document['id'])['ok']


def test_a_locked_voice_refuses_a_silent_change_of_reference(voices, tmp_path):
    document = stable.create('Nymphaea', _wav(tmp_path / 'take.wav', 15.0), 'Bonjour.')
    document['model'] = '0.6B-Base'
    with pytest.raises(CyToolError) as failure:
        stable.update(document)
    assert 'locked' in str(failure.value).lower()


def test_removing_a_voice_keeps_the_recording(voices, tmp_path):
    document = stable.create('Nymphaea', _wav(tmp_path / 'take.wav', 15.0), 'Bonjour.')
    result = stable.remove(document['id'])
    assert not stable.exists(document['id'])
    kept = list(Path(result['trash']).iterdir())
    assert any(item.suffix == '.wav' for item in kept)


def test_clone_parameters_carry_what_a_clone_needs(voices, tmp_path):
    document = stable.create('Nymphaea', _wav(tmp_path / 'take.wav', 15.0), 'Bonjour.')
    parameters = stable.clone_parameters(document)
    assert parameters['mode'] == 'clone'
    assert parameters['reference_text'] == 'Bonjour.'
    assert Path(parameters['reference_audio']).is_file()
