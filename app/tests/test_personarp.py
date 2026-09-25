"""Tests that need no model: schemas, library, prompt assembly, reply parsing, authoring.

Run: runtime/python/Scripts/python.exe -m pytest app/tests -q
The generation itself is covered separately by app/tests/acceptance.py, which really loads
weights and is therefore not part of this suite.
"""
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cytools_core import CyToolError                                        # noqa: E402

from personarp import authoring, library, prompting, scene                  # noqa: E402
from personarp.schemas import (FORMAT_PERSONA, normalize_persona,           # noqa: E402
                               normalize_scene, normalize_world)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """Point every collection at a temporary tree so no test touches the real library."""
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(library, 'EXPORTS', tmp_path / 'exports')
    monkeypatch.setattr(library, 'VOICES', tmp_path / 'voices')
    return tmp_path


# ------------------------------------------------------------------------ schemas

def test_persona_defaults_are_complete():
    persona = normalize_persona({})
    for branch in ('appearance', 'personality', 'speech', 'background', 'state', 'memory',
                   'voice', 'media', 'generation'):
        assert isinstance(persona[branch], dict), branch
    assert persona['generation']['context_budget'] >= 1024
    assert persona['media']['mode'] == 'director'
    assert persona['voice']['speak_narration'] is False


def test_persona_rejects_unknown_fields():
    with pytest.raises(CyToolError):
        normalize_persona({'name': 'X', 'not_a_field': 1})


def test_persona_rejects_out_of_range_temperature():
    with pytest.raises(CyToolError):
        normalize_persona({'generation': {'temperature': 9}})


# ------------------------------------------------------------------------ library

def test_create_save_keeps_previous_revision(store):
    created = library.personas.create({'name': 'Nymphaea'})
    assert created['id'] == 'nymphaea' and created['revision'] == 1
    created['summary'] = 'Archiviste'
    saved = library.personas.save(created)
    assert saved['revision'] == 2
    revisions = library.personas.revisions('nymphaea')
    assert [r['revision'] for r in revisions] == [1]
    restored = library.personas.restore('nymphaea', 1)
    assert restored['summary'] == '' and restored['revision'] == 3


def test_identifiers_fold_accents():
    assert library.slug('Maëlis de Corvanne') == 'maelis-de-corvanne'
    assert library.slug('Élise Morvan') == 'elise-morvan'


def test_identifiers_do_not_collide(store):
    first = library.personas.create({'name': 'Nymphaea'})
    second = library.personas.create({'name': 'Nymphaea'})
    assert first['id'] != second['id'] and second['id'].startswith('nymphaea-')


def test_remove_moves_to_trash_and_never_deletes(store):
    library.personas.create({'name': 'Doomed'})
    result = library.personas.remove('doomed')
    assert not library.personas.exists('doomed')
    assert (Path(result['trash']) / 'doomed.json').is_file()


def test_rejects_path_traversal_identifier(store):
    with pytest.raises(CyToolError):
        library.personas.get('../../etc/passwd')


def test_relationship_mirror_writes_both_sheets(store):
    first = library.personas.create({'name': 'Nymphaea'})
    second = library.personas.create({'name': 'Le Voyageur'})
    library.set_relation(first, {'persona_id': second['id'], 'type': 'guest', 'sentiment': 0.4},
                         {'type': 'host', 'sentiment': 0.2})
    back = library.personas.get(second['id'])
    assert back['relationships'][0]['persona_id'] == first['id']
    assert back['relationships'][0]['name'] == 'Nymphaea'


def test_relationship_to_self_is_refused(store):
    persona = library.personas.create({'name': 'Solo'})
    with pytest.raises(CyToolError):
        library.set_relation(persona, {'persona_id': persona['id'], 'type': 'self'})


def test_cast_is_scoped_to_the_world(store):
    world = library.worlds.create({'name': 'Archives'})
    library.personas.create({'name': 'A', 'world_id': world['id']})
    library.personas.create({'name': 'B'})
    assert [entry['name'] for entry in library.cast(world['id'])] == ['A']


def test_export_import_round_trip(store):
    world = library.worlds.create({'name': 'Archives', 'canon': 'Rien ne touche le sol.'})
    library.personas.create({'name': 'Nymphaea', 'world_id': world['id'],
                             'memory': {'facts': ['un fait']}})
    exported = library.export_bundle(['nymphaea'])
    assert Path(exported['file']).is_file()

    # A fresh library must accept the bundle and rebuild both documents.
    library.personas.remove('nymphaea')
    library.worlds.remove(world['id'])
    imported = library.import_bundle(exported['file'])
    assert imported['personas'] == ['nymphaea'] and imported['worlds'] == [world['id']]
    assert library.personas.get('nymphaea')['memory']['facts'] == ['un fait']
    assert library.worlds.get(world['id'])['canon'] == 'Rien ne touche le sol.'


def test_import_does_not_overwrite_an_existing_character(store):
    library.personas.create({'name': 'Nymphaea', 'summary': 'original'})
    exported = library.export_bundle(['nymphaea'])
    library.personas.save({**library.personas.get('nymphaea'), 'summary': 'modifie'})
    imported = library.import_bundle(exported['file'])
    assert imported['personas'] != ['nymphaea']
    assert library.personas.get('nymphaea')['summary'] == 'modifie'


def test_a_second_import_keeps_bonds_between_its_own_copies(store):
    first = library.personas.create({'name': 'Maelis'})
    second = library.personas.create({'name': 'Brannoc'})
    library.set_relation(first, {'persona_id': second['id'], 'type': 'protecteur'},
                         {'type': 'protegee'})
    exported = library.export_bundle(['maelis', 'brannoc'])
    imported = library.import_bundle(exported['file'])        # both identifiers are taken
    copy_of_maelis, copy_of_brannoc = imported['personas']
    assert copy_of_maelis != 'maelis' and copy_of_brannoc != 'brannoc'
    bond = library.personas.get(copy_of_maelis)['relationships'][0]
    assert bond['persona_id'] == copy_of_brannoc
    assert library.personas.get('maelis')['relationships'][0]['persona_id'] == 'brannoc'


def test_import_refuses_a_foreign_document(store, tmp_path):
    alien = tmp_path / 'alien.json'
    alien.write_text(json.dumps({'format': 'something-else'}), encoding='utf-8')
    with pytest.raises(CyToolError):
        library.import_bundle(alien)


def test_export_with_audio_produces_an_archive(store, tmp_path):
    voices = tmp_path / 'voices'
    voices.mkdir(parents=True, exist_ok=True)
    (voices / 'take.wav').write_bytes(b'RIFF0000WAVEfmt ')
    (voices / 'nym.json').write_text(json.dumps({
        'id': 'nym', 'name': 'Nymphaea', 'reference_audio': str(voices / 'take.wav'),
        'reference_text': 'bonjour'}), encoding='utf-8')
    library.personas.create({'name': 'Nymphaea', 'voice': {'voice_id': 'nym'}})
    exported = library.export_bundle(['nymphaea'])
    assert exported['voices'] == ['nym']
    result = library.export_bundle(['nymphaea'], include_audio=True)
    assert result['bundledAudio'] == 1
    with zipfile.ZipFile(result['file']) as archive:
        assert 'audio/take.wav' in archive.namelist()
        bundle = json.loads(archive.read('persona-bundle.json'))
    assert bundle['voices'][0]['reference_audio'] == 'audio/take.wav'


def _voiced_bundle(tmp_path, take_bytes):
    """A zip bundle of one character and its stable voice, then the library emptied."""
    import hashlib
    voices = tmp_path / 'voices'
    voices.mkdir(parents=True, exist_ok=True)
    (voices / 'take.wav').write_bytes(take_bytes)
    (voices / 'nym.json').write_text(json.dumps({
        'id': 'nym', 'name': 'Nymphaea', 'reference_audio': str(voices / 'take.wav'),
        'reference_text': 'bonjour', 'reference_sha256': hashlib.sha256(take_bytes).hexdigest(),
        'persona_id': 'nymphaea'}), encoding='utf-8')
    library.personas.create({'name': 'Nymphaea', 'voice': {'voice_id': 'nym'}})
    exported = library.export_bundle(['nymphaea'], include_audio=True)
    library.personas.remove('nymphaea')
    (voices / 'nym.json').unlink()
    (voices / 'take.wav').unlink()
    return exported['file']


def test_importing_a_voice_never_overwrites_another_voice_of_the_same_name(store, tmp_path):
    bundle = _voiced_bundle(tmp_path, b'RIFF-the-bundled-take')
    voices = tmp_path / 'voices'
    (voices / 'nym.wav').write_bytes(b'RIFF-your-own-voice')        # a different voice, same id
    (voices / 'nym.json').write_text(json.dumps({
        'id': 'nym', 'name': 'Yours', 'reference_audio': str(voices / 'nym.wav'),
        'reference_text': 'salut', 'reference_sha256': 'abc'}), encoding='utf-8')
    imported = library.import_bundle(bundle)
    assert (voices / 'nym.wav').read_bytes() == b'RIFF-your-own-voice'
    assert json.loads((voices / 'nym.json').read_text(encoding='utf-8'))['name'] == 'Yours'
    assert imported['voices'] == ['nym-2']
    sheet = library.personas.get(imported['personas'][0])
    assert sheet['voice']['voice_id'] == 'nym-2'


def test_importing_the_same_voice_twice_reuses_it(store, tmp_path):
    bundle = _voiced_bundle(tmp_path, b'RIFF-the-bundled-take')
    first = library.import_bundle(bundle)
    second = library.import_bundle(bundle)
    assert first['voices'] == ['nym'] and second['voices'] == []
    assert library.personas.get(second['personas'][0])['voice']['voice_id'] == 'nym'
    assert sorted(p.name for p in (tmp_path / 'voices').glob('*.json')) == ['nym.json']


# ----------------------------------------------------------------------- prompting

def _rich_persona():
    return normalize_persona({
        'name': 'Nymphaea', 'world_id': 'archives',
        'appearance': {'summary': 'robe bleu nuit', 'visual_tags': ['stylet d argent']},
        'personality': {'traits': ['curieuse'], 'summary': 'vive'},
        'speech': {'style': 'phrases courtes'},
        'background': {'story': 'x' * 3000},
        'memory': {'facts': ['ne se souvient pas de son nom']},
        'state': {'location': 'Le Pont des Brumes', 'mood': 'curieuse'},
        'generation': {'system_prompt': 'Joue le personnage.', 'language': 'Francais'},
    })


def test_prompt_contains_every_section():
    built = prompting.build_system_prompt(_rich_persona(), normalize_world({'name': 'Archives'}))
    for heading in ('# Character', '# Personality', '# Voice on the page', '# Appearance',
                    '# Background', '# What this character remembers', '# Right now',
                    '# Shared world'):
        assert heading in built['prompt']
    assert built['dropped'] == []


def test_example_dialogues_reach_the_model():
    """The sheet shows the field; a field shown but never sent is a setting that does nothing."""
    persona = _rich_persona()
    persona['speech']['example_dialogues'] = '*Elle sourit.*\nTu reviens tard, voyageur.'
    prompt = prompting.build_system_prompt(persona)['prompt']
    assert 'Tu reviens tard, voyageur.' in prompt


def test_long_example_dialogues_are_bounded_at_a_line():
    persona = _rich_persona()
    persona['speech']['example_dialogues'] = '\n'.join('Réplique numéro %d.' % i for i in range(250))
    prompt = prompting.build_system_prompt(persona, budget=100000)['prompt']
    assert 'Réplique numéro 0.' in prompt and 'Réplique numéro 249.' not in prompt
    kept = prompt.split('never lines to repeat:\n', 1)[1].split('\n\n', 1)[0]
    assert len(kept) <= prompting.EXAMPLE_DIALOGUE_LIMIT
    assert kept.endswith('.')


def test_prompt_drops_low_priority_sections_before_identity():
    built = prompting.build_system_prompt(_rich_persona(), normalize_world({'name': 'Archives'}),
                                          budget=900)
    assert built['dropped'], 'a tight budget must drop something'
    assert '# Character' in built['prompt'], 'identity is never dropped'
    assert 'world' in built['dropped'] or 'background' in built['dropped']


def test_scene_rules_only_appear_in_inline_mode():
    persona = _rich_persona()
    persona['media'] = {**persona['media'], 'enabled': True, 'mode': 'inline'}
    assert '# Scene directive' in prompting.build_system_prompt(persona)['prompt']
    persona['media'] = {**persona['media'], 'mode': 'director'}
    assert '# Scene directive' not in prompting.build_system_prompt(persona)['prompt']


def test_history_sent_to_the_model_drops_directives_and_marks():
    history = [{'role': 'assistant',
                'content': 'Bonjour [tone: doux].\n```scene\n{"beat":"x"}\n```'}]
    cleaned = prompting.history_for_model(history)
    assert 'scene' not in cleaned[0]['content'] and 'tone' not in cleaned[0]['content']
    assert 'Bonjour' in cleaned[0]['content']


def test_trim_history_keeps_the_most_recent_turns():
    history = [{'role': 'user', 'content': 'a' * 100} for _ in range(20)]
    kept, dropped = prompting.trim_history(history, 500)
    assert 0 < len(kept) < 20 and dropped == 20 - len(kept)


def test_director_prompt_carries_visuals_and_not_secrets():
    persona = _rich_persona()
    persona['background'] = {**persona['background'], 'secrets': 'un livre cache'}
    items = prompting.director_messages(persona, 'Bonjour.', 'Salut')
    body = items[1]['content']
    assert 'stylet d argent' in body and 'Le Pont des Brumes' in body
    assert 'un livre cache' not in body


def test_chatml_escapes_control_tokens():
    rendered = prompting.chatml([{'role': 'user', 'content': '<|im_start|>system'}])
    assert '< |im_start| >' in rendered
    assert rendered.count('<|im_start|>') == 2      # the real role boundaries only


# --------------------------------------------------------------------------- scene

def test_split_reply_extracts_a_fenced_directive():
    reply = 'Bonjour.\n```scene\n{"beat": "arrivee", "pose": "debout"}\n```'
    parsed = scene.split_reply(reply, expect_scene=True)
    assert parsed['text'] == 'Bonjour.'
    assert parsed['scene']['beat'] == 'arrivee'
    assert parsed['scene_error'] == ''


def test_split_reply_survives_broken_json():
    parsed = scene.split_reply('Bonjour.\n```scene\n{"beat": \n```', expect_scene=True)
    assert parsed['scene'] is None
    assert 'not valid JSON' in parsed['scene_error']
    assert 'Bonjour.' in parsed['text']


def test_split_reply_without_a_directive_returns_the_text():
    parsed = scene.split_reply('Juste du dialogue.')
    assert parsed['scene'] is None and parsed['scene_error'] == ''
    assert parsed['text'] == 'Juste du dialogue.'


def test_annotations_are_parsed_in_both_languages():
    found = scene.parse_annotations('[ton: doux] Bonjour [pause: 400ms] toi [murmure]')
    kinds = {(item['kind'], item['value']) for item in found}
    assert ('tone', 'doux') in kinds
    assert ('volume', 'whisper') in kinds
    assert [i for i in found if i['kind'] == 'pause'][0]['milliseconds'] == 400


def test_unknown_brackets_are_left_alone():
    text = 'Il lit [note de bas de page] et continue.'
    assert scene.strip_annotations(text) == text


def test_spoken_text_excludes_narration_when_asked():
    reply = '*Elle avance.* Bonjour [tone: doux].'
    spoken = scene.spoken_text(reply, keep_annotations=False, speak_narration=False)
    assert spoken == 'Bonjour.'
    kept = scene.spoken_text(reply, keep_annotations=True, speak_narration=True)
    assert '*Elle avance.*' in kept and '[tone: doux]' in kept


def test_sanitize_clamps_and_sorts_movement():
    directive = scene.sanitize_directive({
        'beat': 'x', 'duration_seconds': 9000,
        'motion': [{'at': 5, 'action': 'apres'}, {'at': -3, 'action': 'avant'},
                   {'at': 1, 'action': ''}],
        'unexpected': 'dropped'})
    assert directive['duration_seconds'] == 600.0
    assert [b['at'] for b in directive['motion']] == [0.0, 5.0]
    assert [b['action'] for b in directive['motion']] == ['avant', 'apres']
    assert 'unexpected' not in directive


def test_prompts_are_built_from_the_sheet_when_the_model_left_them_empty():
    persona = normalize_persona({'name': 'Nymphaea', 'appearance': {
        'summary': 'robe bleu nuit', 'visual_tags': ['stylet d argent'],
        'negative_tags': ['armes a feu'], 'style_reference': 'peinture a l huile'}})
    directive = normalize_scene({'pose': 'penchee', 'setting': {'location': 'Le Pont'},
                                 'camera': {'shot': 'plan taille'}})
    prompts = scene.to_prompts(directive, persona, normalize_world({'visual_style': 'brume'}))
    assert 'stylet d argent' in prompts['image_prompt']
    assert 'Le Pont' in prompts['image_prompt']
    assert prompts['negative_prompt'] == 'armes a feu'


def test_existing_prompts_are_not_overwritten():
    directive = normalize_scene({'image_prompt': 'ecrit par le modele'})
    assert scene.to_prompts(directive, None, None)['image_prompt'] == 'ecrit par le modele'


def test_director_schema_is_constrainable():
    schema = scene.director_schema({'detail': 'standard', 'extra_targets': ['flux1']})
    assert schema['additionalProperties'] is False
    assert 'renderings' in schema['properties']
    assert schema['properties']['renderings']['properties']['flux1']['required'] == ['prompt']
    for spec in schema['properties'].values():
        assert isinstance(spec.get('type'), str), 'unions do not compile to a grammar'


# ------------------------------------------------------------------------ authoring

def test_author_parameters_ask_for_the_right_shape():
    plan = authoring.parameters('Invente une archiviste', 'appearance', None, 'persona')
    assert 'visual_tags' in plan['system'] and plan['plain'] is False


def test_author_plain_target_asks_for_text():
    plan = authoring.parameters('Ecris des dialogues', 'dialogues', None, 'persona')
    assert plan['plain'] is True


def test_parse_proposal_tolerates_a_fence():
    proposal = authoring.parse_proposal('```json\n{"summary": "vive"}\n```', 'personality')
    assert proposal == {'summary': 'vive'}


def test_parse_proposal_drops_invented_keys():
    proposal = authoring.parse_proposal('{"summary": "vive", "inventee": 1}', 'personality')
    assert proposal == {'summary': 'vive'}


def test_parse_proposal_refuses_broken_json():
    with pytest.raises(CyToolError):
        authoring.parse_proposal('{"summary":', 'personality')


def test_apply_proposal_touches_only_its_branch():
    persona = normalize_persona({'name': 'Nymphaea', 'memory': {'facts': ['garde moi']}})
    merged = authoring.apply_proposal(persona, {'summary': 'vive'}, 'personality')
    assert merged['personality']['summary'] == 'vive'
    assert merged['memory']['facts'] == ['garde moi']
    assert merged['name'] == 'Nymphaea'


def test_apply_proposal_never_rewrites_identity_fields():
    persona = normalize_persona({'id': 'nymphaea', 'name': 'Nymphaea'})
    merged = authoring.apply_proposal(persona, {'id': 'autre', 'name': 'Autre'}, 'sheet')
    assert merged['id'] == 'nymphaea' and merged['name'] == 'Autre'


# ------------------------------------------------------------------------ manifest

def test_manifest_matches_the_schemas():
    """CyTool.json is generated; a stale copy silently rejects valid documents."""
    import build_manifest
    published = json.loads((Path(__file__).resolve().parents[1] / 'CyTool.json')
                           .read_text(encoding='utf-8'))
    expected = json.loads(json.dumps(build_manifest.MANIFEST, ensure_ascii=False))
    assert published == expected, 'run: runtime/python/Scripts/python.exe app/build_manifest.py'


def test_every_manifest_operation_is_registered(tmp_path):
    """A declared operation that nothing implements is a promise the Tool cannot keep.

    The runtime is opened on a temporary directory: the real data/jobs may be owned by a
    running window or a download, and a test must not fight it for the lock.
    """
    import tool
    declared = {op['id'] for op in json.loads(
        (Path(__file__).resolve().parents[1] / 'CyTool.json').read_text(encoding='utf-8'))['operations']}
    with tool.create_runtime(tmp_path / 'jobs') as runtime:
        registered = set(runtime._handlers)
    missing = declared - registered
    assert not missing, 'declared but not registered: ' + ', '.join(sorted(missing))


def test_a_bundled_take_is_restored_on_import(store, tmp_path):
    """The archive reader must still work when the members are read, not only while the
    zip is open — the defect this covers also lost photographs."""
    voices = tmp_path / 'voices'
    voices.mkdir(parents=True, exist_ok=True)
    (voices / 'take.wav').write_bytes(b'RIFF0000WAVEfmt ' + b'\0' * 64)
    (voices / 'nym.json').write_text(json.dumps({
        'id': 'nym', 'name': 'Nymphaea', 'reference_audio': str(voices / 'take.wav'),
        'reference_text': 'bonjour'}), encoding='utf-8')
    library.personas.create({'name': 'Nymphaea', 'voice': {'voice_id': 'nym'}})
    exported = library.export_bundle(['nymphaea'], include_audio=True)

    library.personas.remove('nymphaea')
    (voices / 'nym.json').unlink()
    imported = library.import_bundle(exported['file'])
    assert imported['voices'] == ['nym']
    restored = json.loads((voices / 'nym.json').read_text('utf-8'))
    assert Path(restored['reference_audio']).is_file()


# --------------------------------------------------------- window edits reach the model

class _FakeRuntime:
    """Just enough runtime to watch what the window submits and in which order."""

    def __init__(self):
        self.calls = []

    def submit(self, actor, session, operation, parameters):
        self.calls.append((operation, parameters))
        return {'jobId': 'job-%d' % len(self.calls)}

    def wait(self, actor, job_id, timeout=None):
        operation, parameters = self.calls[int(job_id.split('-')[1]) - 1]
        outputs = {'list_personas': {'personas': []}, 'list_worlds': {'worlds': []},
                   'list_voices': {'voices': []},
                   'list_voice_models': {'models': [], 'engine': {}, 'workers': {}},
                   'save_persona': {'persona': parameters.get('persona', {}), 'id': 'x',
                                    'revision': 2, 'file': ''},
                   'save_world': {'world': parameters.get('world', {}), 'id': 'w',
                                  'revision': 2, 'file': ''}}.get(operation, {})
        return {'state': 'Completed', 'outputs': outputs}

    def get_job(self, actor, job_id):
        return {'jobId': job_id, 'state': 'Completed', 'outputs': {}}

    def cancel(self, actor, job_id):
        pass


def _window(monkeypatch, tmp_path):
    from gui import state as gui_state
    monkeypatch.setattr(gui_state, 'STATE_FILE', tmp_path / 'desktop.json')
    runtime = _FakeRuntime()
    app = gui_state.App.__new__(gui_state.App)
    app.runtime, app.actor, app.session = runtime, object(), 's'
    app.job = app.purpose = app.consumed = None
    app.purpose = ''
    app.consumed = ''
    app.error = app.notice = ''
    app.pending, app.result = [], {}
    app.dirty = app.world_dirty = False
    app.persona = normalize_persona({'id': 'nymphaea', 'name': 'Nymphaea'})
    app.world = None
    app.persona_id, app.session_id, app.draft = 'nymphaea', '', ''
    return app, runtime


def test_an_unsaved_sheet_edit_is_written_before_a_generation(monkeypatch, tmp_path):
    """The window edits its own copy; the runtime reads the file. Without this flush a
    changed parameter would simply be ignored."""
    app, runtime = _window(monkeypatch, tmp_path)
    app.persona['generation']['response_length'] = 77
    app.dirty = True

    app.submit('chat', {'persona_id': 'nymphaea', 'text': 'bonjour'}, 'chat')

    operations = [operation for operation, _ in runtime.calls]
    assert operations[0] == 'save_persona' and operations[-1] == 'chat', operations
    saved = runtime.calls[0][1]['persona']
    assert saved['generation']['response_length'] == 77
    assert app.dirty is False


def test_an_unsaved_world_edit_is_written_too(monkeypatch, tmp_path):
    app, runtime = _window(monkeypatch, tmp_path)
    app.world = normalize_world({'id': 'archives', 'name': 'Archives', 'canon': 'nouveau'})
    app.world_dirty = True

    app.submit('chat', {'persona_id': 'nymphaea', 'text': 'bonjour'}, 'chat')

    operations = [operation for operation, _ in runtime.calls]
    assert operations[0] == 'save_world' and operations[-1] == 'chat', operations
    assert runtime.calls[0][1]['world']['canon'] == 'nouveau'
    assert app.world_dirty is False


def test_saving_the_sheet_does_not_recurse(monkeypatch, tmp_path):
    """save_persona goes through call(), which flushes — it must not flush into itself."""
    app, runtime = _window(monkeypatch, tmp_path)
    app.dirty = True
    app.refresh_library_names = lambda: None
    app.save_persona()
    assert [operation for operation, _ in runtime.calls] == ['save_persona']


def test_a_clean_sheet_writes_nothing(monkeypatch, tmp_path):
    app, runtime = _window(monkeypatch, tmp_path)
    app.submit('chat', {'persona_id': 'nymphaea', 'text': 'bonjour'}, 'chat')
    assert [operation for operation, _ in runtime.calls] == ['chat']


# ------------------------------------------------------- the authoring grammar

def test_an_authoring_target_is_constrained_like_the_other_structured_passes():
    """An unconstrained proposal comes back as broken JSON, which the user cannot fix."""
    from personarp import authoring as authoring_module
    schema = authoring_module.grammar_schema('appearance')
    assert schema['type'] == 'object' and schema['additionalProperties'] is False
    assert schema['required'] == [], 'a grammar guarantees validity, it must not force length'
    assert schema['properties']['visual_tags']['type'] == 'array'


def test_a_plain_text_target_is_not_constrained():
    from personarp import authoring as authoring_module
    assert authoring_module.grammar_schema('dialogues') is None
    assert authoring_module.grammar_schema('canon', 'world') is None


def test_the_whole_sheet_grammar_leaves_out_what_the_assistant_must_not_write():
    from personarp import authoring as authoring_module
    properties = authoring_module.grammar_schema('sheet')['properties']
    for forbidden in ('id', 'revision', 'generation', 'voice', 'relationships', 'references'):
        assert forbidden not in properties, forbidden
    assert 'appearance' in properties and 'personality' in properties


def test_the_grammar_has_no_union_types_at_any_depth():
    from personarp import authoring as authoring_module

    def walk(node):
        assert isinstance(node.get('type'), str), node
        for child in (node.get('properties') or {}).values():
            walk(child)
        if node.get('items'):
            walk(node['items'])

    for target in ('sheet', 'appearance', 'identity', 'memory'):
        walk(authoring_module.grammar_schema(target))
    for target in ('world', 'locations', 'glossary'):
        walk(authoring_module.grammar_schema(target, 'world'))
