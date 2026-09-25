"""Translation and per-language voices, with no model loaded.

The language model is replaced by a stub that answers the constrained JSON a translator
would; what is checked is everything around it — what the model is asked, what is stored,
what is refused, and which voice each language ends up with. The real translation and the
real takes are covered by app/tests/acceptance_translation.py.
"""
import json
import re
import struct
import sys
import tempfile
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cytools_core import CyToolError                                        # noqa: E402

import tool                                                                 # noqa: E402
from personarp import library, sessions, translation                        # noqa: E402
from personarp.schemas import FORMAT_PERSONA, normalize_persona, normalize_world  # noqa: E402
from personarp.voice import delivery, stable                                # noqa: E402


# ------------------------------------------------------------------ the marks

def test_marks_are_masked_and_put_back():
    masked, marks = translation.protect('[ton: sourd] Je sais. [pause: 400ms] Va-t-en.')
    assert '[' not in masked and marks == ['[ton: sourd]', '[pause: 400ms]']
    back, lost = translation.restore(masked.replace('Je sais.', 'I know.'), marks)
    assert back == '[ton: sourd] I know. [pause: 400ms] Va-t-en.' and lost == []


def test_a_lost_mark_is_reported_and_an_invented_one_dropped():
    masked, marks = translation.protect('[ton: sourd] Non. [pause: 1s] Jamais.')
    answer = 'No. ⟦2⟧ Never. ⟦7⟧'                           # ⟦1⟧ lost, ⟦7⟧ invented
    back, lost = translation.restore(answer, marks)
    assert lost == ['[ton: sourd]']
    assert back == 'No. [pause: 1s] Never.'


def test_a_token_repeated_by_the_model_is_used_once():
    back, lost = translation.restore('⟦1⟧ Yes. ⟦1⟧ Yes.', ['[ton: doux]'])
    assert back.count('[ton: doux]') == 1 and lost == []


def test_the_scene_directive_is_not_translated():
    turn = {'role': 'assistant',
            'content': 'Je reste.\n```scene\n{"kind": "cy.persona.scene", "beat": "x"}\n```'}
    assert translation.translatable(turn) == 'Je reste.'


def test_batches_never_split_a_turn_and_stay_bounded():
    entries = [('turn_%d' % i, 'x' * 900) for i in range(5)]
    groups = list(translation.batches(entries, limit=2000))
    assert [len(group) for group in groups] == [2, 2, 1]
    assert [key for group in groups for key, _ in group] == [key for key, _ in entries]


def test_the_schema_demands_every_turn():
    schema = translation.batch_schema([('turn_1', 'Bonjour'), ('turn_2', 'Salut')])
    assert schema['required'] == ['turn_1', 'turn_2']
    assert schema['additionalProperties'] is False
    assert all(spec['minLength'] == 1 for spec in schema['properties'].values())


def test_an_answer_missing_a_turn_is_an_error():
    with pytest.raises(CyToolError) as failure:
        translation.parse('{"turn_1": "Hello"}', [('turn_1', 'a'), ('turn_2', 'b')])
    assert 'turn_2' in str(failure.value)


def test_the_request_names_the_languages_and_protects_the_names():
    items = translation.messages([('turn_1', 'Bonjour ⟦1⟧')], target='English', source='French',
                                 names=['Alcyone', ''], speakers={'turn_1': 'Alcyone'})
    assert 'from French into English' in items[0]['content']
    assert 'Alcyone' in items[0]['content'] and '⟦1⟧' in items[1]['content']


def test_an_unknown_target_language_is_refused():
    with pytest.raises(CyToolError):
        translation.messages([('text', 'a')], target='Klingon')


# ------------------------------------------------------------ voice per language

def _wav(path, seconds=15.0, rate=24000):
    frames = int(seconds * rate)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack('<%dh' % frames, *([0] * frames)))
    return path


@pytest.fixture()
def installed(tmp_path, monkeypatch):
    """Every Qwen3-TTS variant installed, and a private voice library."""
    models = {'base': {'backend': 'qwen3tts', 'variant': '1.7B-Base'},
              'custom': {'backend': 'qwen3tts', 'variant': '1.7B-CustomVoice'},
              'design': {'backend': 'qwen3tts', 'variant': '1.7B-VoiceDesign'}}
    monkeypatch.setattr(delivery.catalog, 'catalog', lambda: models)
    monkeypatch.setattr(delivery.catalog, 'installed', lambda key: True)
    monkeypatch.setattr(delivery.catalog, 'directory', lambda key: Path('/models') / key)
    folder = tmp_path / 'voices'
    folder.mkdir()
    monkeypatch.setattr(stable, 'VOICES', folder)
    french = stable.create('Alcyone FR', _wav(tmp_path / 'fr.wav'), 'Bonjour.', language='French')
    english = stable.create('Alcyone EN', _wav(tmp_path / 'en.wav'), 'Hello.', language='English')
    return {'french': french, 'english': english}


def _sheet(voice_id='', language='French', languages=(), **voice):
    return normalize_persona({'name': 'Alcyone', 'voice': {
        'voice_id': voice_id, 'language': language, 'languages': list(languages), **voice}})


def test_without_a_language_the_character_speaks_its_own(installed):
    payload, note = delivery.payload_for(_sheet(installed['french']['id']), 'Bonjour.')
    assert payload['mode'] == 'clone' and payload['language'] == 'French'
    assert payload['x_vector_only'] is False and note == ''


def test_the_sheet_language_wins_over_the_voice_language(installed):
    payload, _ = delivery.payload_for(_sheet(installed['french']['id'], language='English'), 'Hi.')
    assert payload['language'] == 'English'


def test_an_unconfigured_language_keeps_the_same_voice_and_its_accent(installed):
    payload, _ = delivery.payload_for(_sheet(installed['french']['id']), 'Hello.',
                                      language='English')
    assert payload['mode'] == 'clone' and payload['language'] == 'English'
    assert payload['reference_audio'] == installed['french']['reference_audio']
    assert payload['x_vector_only'] is False
    assert payload['voice_plan']['configured'] is False
    assert payload['voice_plan']['accent'] == 'keep'


def test_native_pronunciation_keeps_only_the_timbre(installed):
    persona = _sheet(installed['french']['id'],
                     languages=[{'language': 'English', 'source': 'same', 'accent': 'native'}])
    payload, _ = delivery.payload_for(persona, 'Hello.', language='English')
    assert payload['reference_audio'] == installed['french']['reference_audio']
    assert payload['x_vector_only'] is True


def test_a_language_can_have_its_own_stable_voice(installed):
    persona = _sheet(installed['french']['id'], languages=[
        {'language': 'English', 'source': 'voice', 'voice_id': installed['english']['id']}])
    english, _ = delivery.payload_for(persona, 'Hello.', language='English')
    french, _ = delivery.payload_for(persona, 'Bonjour.')
    assert english['reference_audio'] == installed['english']['reference_audio']
    assert english['reference_text'] == 'Hello.' and english['language'] == 'English'
    assert english['voice_plan']['voice_id'] == installed['english']['id']
    assert french['reference_audio'] == installed['french']['reference_audio']


def test_a_missing_language_voice_falls_back_and_says_so(installed):
    persona = _sheet(installed['french']['id'], languages=[
        {'language': 'English', 'source': 'voice', 'voice_id': 'gone'}])
    payload, note = delivery.payload_for(persona, 'Hello.', language='English')
    assert payload['reference_audio'] == installed['french']['reference_audio']
    assert 'not in the library' in note and "own voice was used" in note


def test_a_language_can_have_an_invented_voice(installed):
    persona = _sheet(installed['french']['id'], languages=[
        {'language': 'English', 'source': 'design',
         'description': 'A low London voice, dry and slow.'}])
    payload, _ = delivery.payload_for(persona, 'Hello.', language='English')
    assert payload['mode'] == 'design' and 'London' in payload['instruction']
    assert 'reference_audio' not in payload


def test_a_language_can_use_a_preset_speaker(installed):
    persona = _sheet(installed['french']['id'], languages=[
        {'language': 'English', 'source': 'preset', 'speaker': 'Aiden',
         'instruction': 'Clipped, formal.'}])
    payload, _ = delivery.payload_for(persona, 'Hello.', language='English')
    assert payload['mode'] == 'custom' and payload['speaker'] == 'Aiden'
    assert 'Clipped, formal.' in payload['instruction']


def test_a_preset_voice_is_told_to_keep_its_accent(installed):
    persona = _sheet('', speaker='Ryan')
    payload, _ = delivery.payload_for(persona, 'Hello.', language='English')
    assert payload['mode'] == 'custom'
    assert 'accent of a native French speaker' in payload['instruction']


def test_an_entry_for_the_own_language_never_replaces_the_main_voice(installed):
    persona = _sheet(installed['french']['id'], languages=[
        {'language': 'French', 'source': 'voice', 'voice_id': installed['english']['id']}])
    for requested in ('', 'French'):
        payload, _ = delivery.payload_for(persona, 'Bonjour.', language=requested)
        assert payload['reference_audio'] == installed['french']['reference_audio']
        assert payload['voice_plan']['configured'] is False


def test_a_language_seed_applies_and_an_explicit_seed_wins(installed):
    persona = _sheet(installed['french']['id'], languages=[
        {'language': 'English', 'source': 'same', 'seed': 7}])
    assert delivery.payload_for(persona, 'Hi.', language='English')[0]['seed'] == 7
    assert delivery.payload_for(persona, 'Hi.', language='English', seed=9)[0]['seed'] == 9


def test_the_seed_of_an_existing_voice_is_unchanged(installed):
    """Earlier takes must stay reproducible after languages were added."""
    payload, _ = delivery.payload_for(_sheet(installed['french']['id']), 'Bonjour.')
    assert payload['seed'] == (-1 & 0x7fffffff)


# -------------------------------------------------------- the operations, end to end

class FakeTranslator:
    """Answers like a translator would, and remembers what it was asked."""

    def __init__(self):
        self.requests = []
        self.drop_marks = False

    def __call__(self, context, settings, items, json_schema=None, progress=(5, 15), fit=True):
        self.requests.append({'settings': settings, 'items': items, 'schema': json_schema})
        body = items[-1]['content'].split(':\n', 1)[1]
        source = json.loads(body[body.index('{'):])
        answer = {}
        for key, value in source.items():
            text = value.replace('Bonjour', 'Hello').replace('Non', 'No')
            if self.drop_marks:
                text = re.sub(r'⟦\d+⟧', '', text)
            answer[key] = 'EN ' + text
        return {'text': json.dumps(answer, ensure_ascii=False), 'truncated': False,
                'seconds': 0.1, 'reused': False}


@pytest.fixture()
def scene_store(tmp_path, monkeypatch, installed):
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(sessions, 'SESSIONS', tmp_path / 'sessions')
    fake = FakeTranslator()
    monkeypatch.setattr(tool.ResidentModel, 'generate',
                        lambda self, *args, **kwargs: fake(*args, **kwargs))
    persona = personas.create(_sheet(installed['french']['id']))
    session = sessions.create(persona['id'], 'Test')
    sessions.append_turn(session, 'user', 'Bonjour Alcyone.')
    sessions.append_turn(session, 'assistant',
                         '[ton: sec] Non. [pause: 400ms] *Elle referme le registre.* Bonjour.')
    sessions.append_turn(session, 'assistant', '[pause: 1s]')
    sessions.save(session)
    return {'persona': persona, 'session': session, 'fake': fake}


def _run(runtime, operation, parameters):
    actor = runtime.authenticate(runtime.create_client('Test', ['filesystemExternal'])['token'])
    session = runtime.create_session(actor, temporary=True)['sessionId']
    job = runtime.submit(actor, session, operation, parameters)
    return runtime.wait(actor, job['jobId'], timeout=60)


def test_a_scene_is_translated_beside_its_original(scene_store, monkeypatch):
    monkeypatch.setattr(tool.models, 'installed', lambda model: True)
    persona, session = scene_store['persona'], scene_store['session']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'persona_id': persona['id'],
                                             'session_id': session['id'],
                                             'target_language': 'English',
                                             'llm_model': 'qwen3-8b'})
    assert result['state'] == 'Completed', result.get('error')
    outputs = result['outputs']
    assert outputs['source'] == 'French' and outputs['model'] == 'qwen3-8b'
    assert [item['turn'] for item in outputs['translations']] == [0, 1]
    assert outputs['skipped'] == [{'turn': 2, 'reason': 'nothing to translate'}]

    stored = sessions.get(persona['id'], session['id'])
    line = stored['turns'][1]
    assert line['content'].startswith('[ton: sec] Non.')            # original untouched
    english = line['translations']['English']['text']
    assert english.startswith('EN [ton: sec] No. [pause: 400ms]')
    assert line['translations']['English']['model'] == 'qwen3-8b'

    request = scene_store['fake'].requests[0]
    assert request['schema']['required'] == ['turn_0', 'turn_1']
    assert request['settings']['temperature'] == 0.2
    assert '[ton:' not in request['items'][-1]['content']           # marks never reach the model
    assert 'Alcyone' in request['items'][0]['content']


def test_translated_lines_are_not_translated_twice(scene_store, monkeypatch):
    monkeypatch.setattr(tool.models, 'installed', lambda model: True)
    persona, session = scene_store['persona'], scene_store['session']
    parameters = {'persona_id': persona['id'], 'session_id': session['id'],
                  'target_language': 'English', 'llm_model': 'qwen3-8b'}
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        _run(runtime, 'translate', parameters)
        again = _run(runtime, 'translate', parameters)['outputs']
        assert again['translations'] == []
        assert {'turn': 0, 'reason': 'already translated'} in again['skipped']
        forced = _run(runtime, 'translate', {**parameters, 'overwrite': True})['outputs']
        assert len(forced['translations']) == 2
    assert len(scene_store['fake'].requests) == 2                   # the skip loaded nothing


def test_lost_marks_are_reported(scene_store, monkeypatch):
    monkeypatch.setattr(tool.models, 'installed', lambda model: True)
    scene_store['fake'].drop_marks = True
    persona, session = scene_store['persona'], scene_store['session']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        outputs = _run(runtime, 'translate', {'persona_id': persona['id'],
                                              'session_id': session['id'],
                                              'target_language': 'English',
                                              'llm_model': 'qwen3-8b'})['outputs']
    assert outputs['marksLost'] == 2
    stored = sessions.get(persona['id'], session['id'])
    assert stored['turns'][1]['translations']['English']['marksLost'] == ['[ton: sec]',
                                                                          '[pause: 400ms]']


def test_a_free_text_can_be_translated(scene_store, monkeypatch):
    monkeypatch.setattr(tool.models, 'installed', lambda model: True)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        outputs = _run(runtime, 'translate', {'text': 'Bonjour.', 'source_language': 'French',
                                              'target_language': 'English',
                                              'llm_model': 'qwen3-8b'})['outputs']
    assert outputs['text'] == 'EN Hello.' and outputs['saved'] is False


def test_translating_into_the_same_language_is_refused(scene_store):
    persona, session = scene_store['persona'], scene_store['session']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'persona_id': persona['id'],
                                             'session_id': session['id'],
                                             'target_language': 'French'})
    assert result['state'] == 'Failed' and 'already in French' in result['error']['message']


def test_an_unknown_translation_model_is_refused(scene_store):
    persona, session = scene_store['persona'], scene_store['session']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'persona_id': persona['id'],
                                             'session_id': session['id'],
                                             'target_language': 'English',
                                             'llm_model': 'no-such-model'})
    assert result['state'] == 'Failed' and result['error']['code'] == 'MissingModel'


def test_speaking_a_line_that_has_no_translation_is_refused(scene_store):
    persona, session = scene_store['persona'], scene_store['session']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        missing = _run(runtime, 'speak_turn', {'persona_id': persona['id'],
                                               'session_id': session['id'], 'turn': 1,
                                               'language': 'German'})
        player = _run(runtime, 'speak_turn', {'persona_id': persona['id'],
                                              'session_id': session['id'], 'turn': 0})
    assert missing['state'] == 'Failed' and 'no German translation' in missing['error']['message']
    assert player['state'] == 'Failed' and "character's lines" in player['error']['message']


def test_a_voice_can_be_attached_to_one_language_only(scene_store, tmp_path):
    persona = scene_store['persona']
    take = _wav(tmp_path / 'english-take.wav')
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'create_stable_voice', {
            'name': 'Alcyone in English', 'audio': str(take), 'transcript': 'Hello there.',
            'persona_id': persona['id'], 'language': 'English', 'for_language': 'English'})
    assert result['state'] == 'Completed', result.get('error')
    assert result['outputs']['forLanguage'] == 'English'
    sheet = library.personas.get(persona['id'])
    assert sheet['voice']['voice_id'] == persona['voice']['voice_id']      # main voice kept
    assert sheet['voice']['languages'] == [{**sheet['voice']['languages'][0],
                                            'language': 'English', 'source': 'voice',
                                            'voice_id': result['outputs']['id']}]
    assert result['outputs']['voice']['model'] == '1.7B-Base'


# ----------------------------------------------- parameters nobody sent stay absent

def test_no_optional_object_parameter_is_filled_by_validation():
    """A defaulted optional object is expanded into a blank document by validation, and that
    blank document then replaces the real one (a mirror bond, a character's voice)."""
    manifest = json.loads((Path(tool.__file__).parent / 'CyTool.json').read_text(encoding='utf-8'))
    offenders = []
    for operation in manifest['operations']:
        schema = operation['inputSchema']
        for name, spec in schema.get('properties', {}).items():
            if spec.get('type') == 'object' and spec.get('properties') and 'default' in spec \
                    and name not in schema.get('required', []):
                offenders.append('%s.%s' % (operation['id'], name))
    assert offenders == []


def test_speaking_as_a_character_uses_its_stable_voice(scene_store, monkeypatch):
    heard = {}

    def fake_speak(context, payload, offset=0.0, scale=1.0):
        heard.update(payload)
        return {'file': str(Path(tempfile.gettempdir()) / 'x.wav'), 'durationSeconds': 1.0,
                'mode': payload['mode'], 'model': payload['model']}
    monkeypatch.setattr(tool.voice_runner, 'speak', fake_speak)
    persona = scene_store['persona']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak', {'persona_id': persona['id'], 'text': 'Bonjour.'})
        assert result['state'] == 'Completed', result.get('error')
        assert heard['mode'] == 'clone'
        assert heard['reference_audio'] == stable.get(persona['voice']['voice_id'])['reference_audio']
        # A partial override changes only what it names.
        result = _run(runtime, 'speak', {'persona_id': persona['id'], 'text': 'Bonjour.',
                                         'voice': {'annotations': False}})
        assert result['state'] == 'Completed' and heard['mode'] == 'clone'
        assert heard['annotations'] is False


def test_a_bond_without_a_mirror_leaves_the_other_sheet_alone(scene_store):
    library.personas.create({'name': 'Brannoc', 'relationships': [
        {'persona_id': 'alcyone', 'type': 'dette', 'history': 'Une vieille dette.'}]})
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'set_relation', {'persona_id': 'alcyone', 'relation': {
            'persona_id': 'brannoc', 'type': 'protecteur', 'history': 'Il la suit.'}})
        assert result['state'] == 'Completed', result.get('error')
        other = library.personas.get('brannoc')['relationships']
        assert other == [{**other[0], 'type': 'dette', 'history': 'Une vieille dette.'}]
        result = _run(runtime, 'set_relation', {'persona_id': 'alcyone', 'mirror': True,
                                                'relation': {'persona_id': 'brannoc',
                                                             'type': 'ami', 'sentiment': 0.6}})
        mirror = library.personas.get('brannoc')['relationships'][0]
        assert mirror['type'] == 'ami' and mirror['sentiment'] == 0.6
        assert mirror['name'] == 'Alcyone'


# ------------------------------------------------------------- the context of the scene

WORLD = {'id': 'valdrenn', 'name': 'Valdrenn', 'genre': 'Fantasy epique',
         'tone': 'Grave et lumineux', 'summary': 'Un continent ancien.',
         'setting': 'Des Marches aux montagnes de Hautroc.',
         'locations': [{'name': 'Corvanne', 'description': 'Cite fortifiee des Marches.'},
                       {'name': 'Hautroc', 'description': 'Montagnes creusees de tunnels, cols '
                                                          'enneiges.'}],
         'factions': [{'name': 'Les Maisons des Marches', 'description': 'Sept maisons rivales.'}],
         'glossary': [{'term': 'Eclat', 'meaning': 'Un morceau de la Couronne des Morts.'},
                      {'term': 'Roi-Cendre', 'meaning': 'Le seigneur de la Legion Cendree.'}]}


def test_the_context_tells_the_world_the_speaker_and_the_moment():
    persona = normalize_persona({
        'name': 'Maelis', 'personality': {'summary': 'Fille d aubergiste obstinee.'},
        'speech': {'style': 'phrases courtes', 'register': 'familier'},
        'state': {'location': 'au pied du col de Hautroc', 'mood': 'inquiete'}})
    block = translation.context_block(normalize_world(WORLD), persona, {'title': 'Le passage'},
                                      'On parle d un col de montagne.', focus='vers Hautroc')
    assert 'World: Valdrenn — Fantasy epique' in block and 'Tone: Grave et lumineux' in block
    assert block.index('Hautroc (') < block.index('Corvanne (')      # the one mentioned first
    assert 'Roi-Cendre = Le seigneur' in block
    assert 'How Maelis speaks: style: phrases courtes; register: familier' in block
    assert 'place: au pied du col de Hautroc' in block and 'mood: inquiete' in block
    assert 'Scene title: Le passage' in block
    assert 'Note from the person asking for the translation: On parle' in block


def test_the_context_stays_bounded():
    # Raw, past what the world schema allows: the block bounds itself whatever it is given.
    world = {**WORLD, 'summary': 'x' * 5000,
             'glossary': [{'term': 't%d' % n, 'meaning': 'm' * 300} for n in range(80)]}
    block = translation.context_block(world, None, None, 'y' * 5000)
    assert len(block) <= translation.CONTEXT_CHARACTERS


def test_the_lines_before_are_shown_in_their_own_words():
    turns = [{'role': 'user', 'content': 'On monte vers Hautroc ?'},
             {'role': 'assistant', 'content': 'Oui, par le col.',
              'translations': {'English': {'text': 'Yes, through the pass.'}}},
             {'role': 'assistant', 'content': '[pause: 1s]'},
             {'role': 'user', 'content': 'Il est ouvert ?'},
             {'role': 'assistant', 'content': 'Le col est ferme.'}]
    lines = translation.earlier_lines(turns, 4, 'English',
                                      speaker_names={'assistant': 'Maelis', 'user': 'the player'},
                                      produced={3: 'Is it open?'})
    assert lines == [('the player', 'On monte vers Hautroc ?', ''),
                     ('Maelis', 'Oui, par le col.', 'Yes, through the pass.'),
                     ('the player', 'Il est ouvert ?', 'Is it open?')]      # a pause says nothing


def test_the_request_carries_the_context_and_forbids_translating_it():
    items = translation.messages([('turn_4', 'Le col est ferme.')], target='English',
                                 source='French', context='World: Valdrenn',
                                 earlier=[('Maelis', 'Oui, par le col.', 'Yes, through the pass.')])
    assert 'never translate it and never copy it into the answer' in items[0]['content']
    user = items[1]['content']
    assert user.index('Context — for understanding only') < user.index('Translate into English')
    assert '- Maelis: Oui, par le col. → Yes, through the pass.' in user


class ContextSpy(FakeTranslator):
    """A translator that remembers the context it was given."""


@pytest.fixture()
def world_store(tmp_path, monkeypatch, installed):
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(sessions, 'SESSIONS', tmp_path / 'sessions')
    fake = ContextSpy()
    monkeypatch.setattr(tool.ResidentModel, 'generate',
                        lambda self, *args, **kwargs: fake(*args, **kwargs))
    monkeypatch.setattr(tool.models, 'installed', lambda model: True)
    world = worlds.create(WORLD)
    persona = personas.create({**_sheet(installed['french']['id']), 'world_id': world['id'],
                               'state': {'location': 'au pied du col de Hautroc'}})
    session = sessions.create(persona['id'], 'Le passage')
    sessions.append_turn(session, 'user', 'On monte vers Hautroc demain ?')
    sessions.append_turn(session, 'assistant', 'Oui, par le col, avant la neige.')
    sessions.append_turn(session, 'user', 'Et ce soir ?')
    sessions.append_turn(session, 'assistant', 'Le col est ferme depuis trois jours.')
    sessions.save(session)
    return {'persona': persona, 'session': session, 'fake': fake, 'world': world}


def test_one_line_is_translated_with_the_lines_before_it(world_store):
    persona, session = world_store['persona'], world_store['session']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'persona_id': persona['id'],
                                             'session_id': session['id'], 'turns': [3],
                                             'target_language': 'English',
                                             'llm_model': 'qwen3-8b'})
    assert result['state'] == 'Completed', result.get('error')
    request = world_store['fake'].requests[0]['items'][1]['content']
    assert 'World: Valdrenn' in request and 'Hautroc (' in request
    assert 'Oui, par le col, avant la neige.' in request                # the line before
    assert 'place: au pied du col de Hautroc' in request
    assert result['outputs']['translations'][0]['turn'] == 3


def test_a_text_can_be_translated_in_the_light_of_a_scene_without_storing_anything(world_store):
    persona, session = world_store['persona'], world_store['session']
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'persona_id': persona['id'],
                                             'session_id': session['id'],
                                             'text': 'Le col est ferme.', 'context': 'En montagne.',
                                             'target_language': 'English',
                                             'llm_model': 'qwen3-8b'})
    outputs = result['outputs']
    assert result['state'] == 'Completed', result.get('error')
    assert outputs['text'].startswith('EN ') and outputs['saved'] is False and outputs['context']
    request = world_store['fake'].requests[0]['items'][1]['content']
    assert 'Le col est ferme depuis trois jours.' in request          # the last lines of the scene
    assert 'Note from the person asking for the translation: En montagne.' in request
    stored = sessions.get(persona['id'], session['id'])
    assert not any(turn.get('translations') for turn in stored['turns'])


def test_a_world_gives_its_context_to_a_text_without_a_character(world_store):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'text': 'Le col est ferme.',
                                             'world_id': world_store['world']['id'],
                                             'source_language': 'French',
                                             'target_language': 'English',
                                             'llm_model': 'qwen3-8b'})
    assert result['state'] == 'Completed', result.get('error')
    request = world_store['fake'].requests[0]['items'][1]['content']
    assert 'World: Valdrenn' in request
    assert 'Keep these names exactly' in world_store['fake'].requests[0]['items'][0]['content']


# ------------------------------------------------------- the terms of the world, kept

def test_the_terms_of_a_world_are_found_whatever_their_form():
    terms = translation.world_terms(normalize_world(WORLD))
    assert {item['term'] for item in terms} == {'Valdrenn', 'Eclat', 'Roi-Cendre', 'Corvanne',
                                                'Hautroc', 'Les Maisons des Marches'}
    named = translation.world_terms({'name': "Les Archives Flottantes — le monde d'en haut"})
    assert named == [{'term': 'Les Archives Flottantes', 'meaning': '', 'kind': 'world'}]
    found = translation.mentioned_terms(terms, 'Les ÉCLATS du roi-cendre, vers Hautroc.')
    assert [item['term'] for item in found] == ['Eclat', 'Roi-Cendre', 'Hautroc']
    assert translation.mentioned_terms(terms, 'Une hautrocaille.') == []    # whole words only


def test_a_required_rendering_is_checked_with_its_plural_and_possessive():
    renderings = {'Roi-Cendre': 'the Ash King', 'Eclat': 'Shard'}
    assert translation.missed_terms('Le Roi-Cendre veut les Eclats.',
                                    "The Ash King's army wants the Shards.", renderings) == []
    assert translation.missed_terms('Le Roi-Cendre veut les Eclats.',
                                    'The Cinder King wants the Shards.', renderings) == ['Roi-Cendre']
    assert translation.missed_terms('Rien ici.', 'Nothing here.', renderings) == []


class TermsFake:
    """Renders terms when asked for them, translates otherwise; remembers every request."""

    def __init__(self, renderings, translate):
        self.renderings, self.translate, self.requests = renderings, translate, []

    def __call__(self, context, settings, items, json_schema=None, progress=(5, 15), fit=True):
        self.requests.append({'items': items, 'schema': json_schema})
        keys = list((json_schema or {}).get('properties', {}))
        if items[0]['content'].startswith('You name things'):
            return {'text': json.dumps({key: self.renderings[key] for key in keys}),
                    'truncated': False, 'seconds': 0.1, 'reused': False}
        body = items[-1]['content'].split('Translate into English:\n', 1)[1]
        source = json.loads(body)
        attempt = sum(1 for request in self.requests
                      if not request['items'][0]['content'].startswith('You name things'))
        answer = {key: self.translate(text, attempt, items[-1]['content'])
                  for key, text in source.items()}
        return {'text': json.dumps(answer, ensure_ascii=False), 'truncated': False,
                'seconds': 0.1, 'reused': False}


@pytest.fixture()
def lexicon_store(tmp_path, monkeypatch, installed):
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(sessions, 'SESSIONS', tmp_path / 'sessions')
    monkeypatch.setattr(tool.models, 'installed', lambda model: True)
    world = worlds.create(WORLD)
    persona = personas.create({**_sheet(installed['french']['id']), 'world_id': world['id']})
    session = sessions.create(persona['id'], 'La guerre')
    sessions.append_turn(session, 'assistant', 'Le Roi-Cendre cherche les Eclats.')
    sessions.append_turn(session, 'assistant', 'Personne ne defie le Roi-Cendre a Hautroc.')
    sessions.save(session)

    def use(fake):
        monkeypatch.setattr(tool.ResidentModel, 'generate',
                            lambda self, *args, **kwargs: fake(*args, **kwargs))
        return fake
    return {'persona': persona, 'session': session, 'world': world, 'use': use}


def _faithful(text, attempt, request):
    return (text.replace('Le Roi-Cendre', 'The Ash King').replace('le Roi-Cendre', 'the Ash King')
            .replace('les Eclats', 'the Shards').replace('Personne ne defie', 'Nobody defies')
            .replace('cherche', 'seeks').replace(' a ', ' in '))


def test_terms_are_rendered_once_recorded_in_the_world_and_required(lexicon_store):
    store = lexicon_store
    fake = store['use'](TermsFake({'Roi-Cendre': 'the Ash King', 'Eclat': 'Shard',
                                   'Hautroc': 'Hautroc'}, _faithful))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        first = _run(runtime, 'translate', {'persona_id': store['persona']['id'],
                                            'session_id': store['session']['id'], 'turns': [0],
                                            'target_language': 'English', 'llm_model': 'qwen3-8b'})
        assert first['state'] == 'Completed', first.get('error')
        outputs = first['outputs']
        assert sorted(outputs['termsLearned']) == ['Eclat', 'Roi-Cendre']
        assert outputs['terms'] == {'Roi-Cendre': 'the Ash King', 'Eclat': 'Shard'}
        assert outputs['termsMissed'] == 0 and outputs['worldId'] == store['world']['id']
        table = library.worlds.get(store['world']['id'])['term_translations']['English']
        assert table['Roi-Cendre']['text'] == 'the Ash King' and table['Roi-Cendre']['source'] == 'model'
        batch = fake.requests[1]['items'][1]['content']
        assert '- Roi-Cendre → the Ash King' in batch and '- Eclat → Shard' in batch

        # A later translation reuses them: no new rendering of the Roi-Cendre, Hautroc only.
        fake.requests.clear()
        second = _run(runtime, 'translate', {'persona_id': store['persona']['id'],
                                             'session_id': store['session']['id'], 'turns': [1],
                                             'target_language': 'English', 'llm_model': 'qwen3-8b'})
        assert second['outputs']['termsLearned'] == ['Hautroc']
        pass_request = fake.requests[0]['items'][1]['content']
        assert 'Hautroc' in pass_request and 'Roi-Cendre' not in pass_request
        assert '- Roi-Cendre → the Ash King' in fake.requests[1]['items'][1]['content']


def test_a_rendering_you_set_is_used_and_never_replaced(lexicon_store):
    store = lexicon_store
    fake = store['use'](TermsFake({'Eclat': 'Shard', 'Roi-Cendre': 'the Ash King'},
                                  lambda text, attempt, request: text.replace(
                                      'Le Roi-Cendre', 'The Cinder King').replace('Eclats', 'Shards')))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        fixed = _run(runtime, 'set_term_translations', {
            'world_id': store['world']['id'], 'language': 'English',
            'terms': [{'term': 'Roi-Cendre', 'text': 'the Cinder King'}]})
        assert fixed['state'] == 'Completed' and fixed['outputs']['changed'] == ['Roi-Cendre']
        result = _run(runtime, 'translate', {'persona_id': store['persona']['id'],
                                             'session_id': store['session']['id'], 'turns': [0],
                                             'target_language': 'English', 'llm_model': 'qwen3-8b'})
        assert result['outputs']['termsLearned'] == ['Eclat']
        assert '- Roi-Cendre → the Cinder King' in fake.requests[-1]['items'][1]['content']
        listed = _run(runtime, 'translation_terms', {'world_id': store['world']['id'],
                                                     'language': 'English'})['outputs']['terms']
        by_term = {item['term']: item for item in listed}
    assert by_term['Roi-Cendre']['text'] == 'the Cinder King'
    assert by_term['Roi-Cendre']['source'] == 'person'
    assert by_term['Eclat']['source'] == 'model' and by_term['Corvanne']['text'] == ''


def test_a_line_that_drops_a_term_is_asked_again_then_reported(lexicon_store):
    store = lexicon_store

    def forgetful(text, attempt, request):
        # The first attempt forgets the Ash King; the second, told again, still does on the
        # second line only.
        if attempt == 1 or 'Hautroc' in text:
            return text.replace('Le Roi-Cendre', 'The Cinder King').replace(
                'le Roi-Cendre', 'the Cinder King').replace('Eclats', 'Shards')
        return _faithful(text, attempt, request)

    fake = store['use'](TermsFake({'Roi-Cendre': 'the Ash King', 'Eclat': 'Shard',
                                   'Hautroc': 'Hautroc'}, forgetful))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'persona_id': store['persona']['id'],
                                             'session_id': store['session']['id'],
                                             'target_language': 'English', 'llm_model': 'qwen3-8b'})
    outputs = result['outputs']
    assert result['state'] == 'Completed', result.get('error')
    assert outputs['termsRetried'] == 2
    assert 'A first attempt did not use these renderings' in fake.requests[-1]['items'][1]['content']
    first, second = outputs['translations']
    assert first['text'].startswith('The Ash King') and first['termsMissed'] == []
    assert second['termsMissed'] == ['Roi-Cendre → the Ash King'] and outputs['termsMissed'] == 1
    stored = sessions.get(store['persona']['id'], store['session']['id'])
    assert stored['turns'][1]['translations']['English']['termsMissed'] == ['Roi-Cendre → the Ash King']


def test_keep_terms_off_renders_for_this_request_only(lexicon_store):
    store = lexicon_store
    store['use'](TermsFake({'Roi-Cendre': 'the Ash King', 'Eclat': 'Shard'}, _faithful))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'translate', {'text': 'Le Roi-Cendre cherche les Eclats.',
                                             'world_id': store['world']['id'],
                                             'source_language': 'French', 'keep_terms': False,
                                             'target_language': 'English', 'llm_model': 'qwen3-8b'})
    assert result['outputs']['text'] == 'The Ash King seeks the Shards.'
    assert library.worlds.get(store['world']['id'])['term_translations'] == {}


def test_an_ordinary_word_is_not_held_to_a_term_of_the_world():
    """« Nommer » is in the glossary of Valdrenn; « il faut nommer les morts » is a verb."""
    renderings = {'Nommer': 'the Naming', 'Roi-Cendre': 'the Ash King'}
    assert translation.used_as_name('Nommer', 'Le Nommer a eu lieu.')
    assert not translation.used_as_name('Nommer', 'Il faut nommer les morts.')
    assert translation.used_as_name('Roi-Cendre', 'le roi-cendre')         # a compound, always
    assert translation.missed_terms('Il faut nommer les morts.', 'We must name the dead.',
                                    renderings) == []
    assert translation.missed_terms('Le Nommer a eu lieu.', 'The rite took place.',
                                    renderings) == ['Nommer']


def test_the_terms_pass_asks_for_names_and_gives_the_meaning_as_a_hint():
    items = translation.terms_messages([{'term': 'Roi-Cendre', 'meaning': 'Le seigneur',
                                         'kind': 'term'}], target='English', source='French',
                                       world=normalize_world(WORLD))
    assert 'a name, never a definition' in items[0]['content']
    assert '- Roi-Cendre  (a term; hint: Le seigneur)' in items[1]['content']
    assert 'it is not to be translated' in items[1]['content']
    assert translation.terms_schema([{'term': 'Roi-Cendre'}])['properties']['Roi-Cendre'][
        'maxLength'] == 44


def test_a_definition_is_not_accepted_as_a_rendering():
    """A 4B model once answered the meaning instead of the name."""
    terms = [{'term': 'Roi-Cendre'}, {'term': 'Eclat'}, {'term': 'Les Maisons des Marches'}]
    kept, rejected = translation.parse_terms(json.dumps({
        'Roi-Cendre': 'The lord of the Ash Legion. No one has seen his face.',
        'Eclat': 'Shard', 'Les Maisons des Marches': 'the Houses of the Marches'}), terms)
    assert kept == {'Eclat': 'Shard', 'Les Maisons des Marches': 'the Houses of the Marches'}
    assert rejected == ['Roi-Cendre']


def test_a_leading_article_is_written_in_lower_case():
    kept, _ = translation.parse_terms(json.dumps({'La Brisure': 'The Shattering',
                                                  'Corvanne': 'Corvanne',
                                                  'Le Gue': 'Le Gué des Rois'}),
                                      [{'term': 'La Brisure'}, {'term': 'Corvanne'},
                                       {'term': 'Le Gue'}])
    assert kept == {'La Brisure': 'the Shattering', 'Corvanne': 'Corvanne',
                    'Le Gue': 'le Gué des Rois'}
    assert translation.lower_article('Theodric') == 'Theodric'           # not an article


def test_a_rendered_world_name_is_no_longer_kept_as_written(lexicon_store):
    store = lexicon_store
    fake = store['use'](TermsFake({}, _faithful))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        _run(runtime, 'set_term_translations', {
            'world_id': store['world']['id'], 'language': 'English',
            'terms': [{'term': 'Valdrenn', 'text': 'the Vale of Drenn'}]})
        _run(runtime, 'translate', {'text': 'Bienvenue a Valdrenn.', 'persona_id':
                                    store['persona']['id'], 'target_language': 'English',
                                    'llm_model': 'qwen3-8b'})
    system, user = fake.requests[-1]['items'][0]['content'], fake.requests[-1]['items'][1]['content']
    assert '- Valdrenn → the Vale of Drenn' in user
    assert 'Keep these names exactly as they are written: Alcyone.' in system


def test_a_term_is_found_when_french_contracts_its_article():
    """« Les Archives Flottantes » is said « aux Archives Flottantes »; « Le Pont des Brumes »,
    « du Pont des Brumes ». Looked for with their article, they were never required."""
    terms = [{'term': 'Les Archives Flottantes'}, {'term': 'Le Pont des Brumes'},
             {'term': "L'Ordre de la Derniere Lampe"}, {'term': 'La Brisure'}]
    text = ("Bienvenue aux Archives Flottantes, au bout du Pont des Brumes ; l'Ordre de la "
            "Derniere Lampe veille depuis la Brisure.")
    assert [item['term'] for item in translation.mentioned_terms(terms, text)] == [
        'Les Archives Flottantes', 'Le Pont des Brumes', "L'Ordre de la Derniere Lampe",
        'La Brisure']
    assert translation.missed_terms('au bout du Pont des Brumes', 'at the end of the Bridge of Mist',
                                    {'Le Pont des Brumes': 'the Bridge of Mists'}) \
        == ['Le Pont des Brumes']
    # Without its article, « La Brisure » is one word: a name only with its capital.
    assert translation.used_as_name('La Brisure', 'depuis la Brisure')
    assert not translation.used_as_name('La Brisure', 'une brisure dans le mur')
