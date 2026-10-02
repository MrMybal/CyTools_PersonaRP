"""The example worlds import cleanly and play without losing part of their sheets.

They ship with the application, so a change to the schemas that breaks one of them breaks
the first thing a new user tries. Every bundle is checked the way the Tool will read it.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from personarp import examples, library, prompting                           # noqa: E402
from personarp.voice import stable                                           # noqa: E402
from personarp.schemas import (FORMAT_BUNDLE, FORMAT_PERSONA, normalize_persona,  # noqa: E402
                               normalize_world)

BUNDLES = examples.bundles()


@pytest.fixture()
def store(tmp_path, monkeypatch):
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(library, 'VOICES', tmp_path / 'voices')
    monkeypatch.setattr(stable, 'VOICES', tmp_path / 'voices')
    return tmp_path


def _bundle(path):
    return library._read_bundle(path)[0]


def test_there_are_examples_of_several_genres():
    genres = {_bundle(path)['worlds'][0]['genre'] for path in BUNDLES}
    assert len(BUNDLES) >= 6 and len(genres) == len(BUNDLES)


@pytest.mark.parametrize('path', BUNDLES, ids=lambda path: path.stem)
def test_an_example_is_a_valid_bundle(path):
    bundle = _bundle(path)
    assert bundle['format'] == FORMAT_BUNDLE and len(bundle['worlds']) == 1
    world = normalize_world(bundle['worlds'][0])
    cast = [normalize_persona(sheet) for sheet in bundle['personas']]
    assert len(cast) >= 3
    ids = {sheet['id'] for sheet in cast}
    for sheet in cast:
        assert sheet['world_id'] == world['id']
        assert sheet['relationships'], sheet['id'] + ' has no bond'
        for bond in sheet['relationships']:
            assert bond['persona_id'] in ids, (sheet['id'], bond['persona_id'])
        assert sheet['voice']['description'], sheet['id'] + ' has nothing to invent a voice from'
        assert sheet['speech']['example_dialogues']
        assert len(sheet['appearance']['visual_tags']) >= 3


@pytest.mark.parametrize('path', BUNDLES, ids=lambda path: path.stem)
def test_no_section_of_an_example_is_dropped_from_its_prompt(path):
    bundle = _bundle(path)
    world = normalize_world(bundle['worlds'][0])
    cast = [normalize_persona(sheet) for sheet in bundle['personas']]
    for sheet in cast:
        others = [{'id': other['id'], 'name': other['name'], 'summary': other['summary'],
                   'world_id': other['world_id']} for other in cast if other is not sheet]
        # The chat's own path: it gives the sheet only part of the budget, so checking the
        # system prompt against the whole budget passed a world that a real reply trimmed.
        built = prompting.messages(sheet, 'Bonjour.', [], world, others)
        assert built['context']['droppedSections'] == [], (sheet['id'], built['context'])
        system = built['messages'][0]['content']
        assert sheet['speech']['example_dialogues'].splitlines()[1] in system
        assert world['canon'][:60] in system


@pytest.mark.parametrize('path', BUNDLES, ids=lambda path: path.stem)
def test_an_example_imports_twice_with_its_bonds_intact(store, path):
    first = library.import_bundle(path)
    second = library.import_bundle(path)
    assert set(first['personas']).isdisjoint(second['personas'])
    copies = set(second['personas'])
    for identifier in second['personas']:
        sheet = library.personas.get(identifier)
        assert sheet['world_id'] == second['worlds'][0]
        for bond in sheet['relationships']:
            assert bond['persona_id'] in copies, (identifier, bond['persona_id'])


def test_the_listing_marks_what_is_already_imported(store):
    before = {item['id']: item for item in examples.listing()}
    assert not any(item['imported'] for item in before.values())
    library.import_bundle(BUNDLES[0])
    after = {item['id']: item for item in examples.listing()}
    assert after[BUNDLES[0].stem]['imported']
    assert after[BUNDLES[0].stem]['characters']


@pytest.mark.parametrize('path', [path for path in BUNDLES if path.suffix == '.zip'],
                         ids=lambda path: path.stem)
def test_every_example_character_arrives_with_its_stable_voice(store, path):
    """An example shipped as an archive carries one locked voice per character."""
    imported = library.import_bundle(path)
    assert len(imported['voices']) == len(imported['personas'])
    for identifier in imported['personas']:
        sheet = library.personas.get(identifier)
        voice = sheet['voice']
        assert voice['enabled'] and voice['voice_id'] in imported['voices'], identifier
        assert stable.verify(voice['voice_id'])['ok'], voice['voice_id']
        document = stable.get(voice['voice_id'])
        assert document['locked'] and document['reference_text']
        low, high = stable.ACCEPTED_SECONDS
        assert low <= document['reference_seconds'] <= high


def test_valdrenn_arrives_with_its_english_names(store):
    """Its lexicon keeps the world's names the same in every English translation."""
    library.import_bundle(next(path for path in BUNDLES if 'valdrenn' in path.name))
    lexicon = library.worlds.get('valdrenn')['term_translations']['English']
    assert len(lexicon) == 20
    assert lexicon['Roi-Cendre']['text'] == 'the Ash King' and lexicon['Éclat']['text'] == 'Shard'
    assert all(entry['source'] == 'person' for entry in lexicon.values())


def test_scenes_travel_with_their_characters_without_their_takes(store, tmp_path, monkeypatch):
    from personarp import sessions
    monkeypatch.setattr(sessions, 'SESSIONS', tmp_path / 'sessions')
    sheet = library.personas.create({'name': 'Wren'})
    scene = sessions.create(sheet['id'], 'Les rayonnages')
    sessions.append_turn(scene, 'user', 'Salut.')
    sessions.append_turn(scene, 'assistant', 'Ouais bon.')
    scene['turns'][1]['audio'] = {'file': str(tmp_path / 'take.wav'), 'takes': []}
    sessions.save(scene)
    alone = library.export_bundle([sheet['id']], destination=str(tmp_path / 'a.json'))
    assert alone['sessions'] == 0                                   # scenes only when asked
    exported = library.export_bundle([sheet['id']], destination=str(tmp_path / 'b.json'),
                                     include_sessions=True)
    assert exported['sessions'] == 1
    carried = json.loads((tmp_path / 'b.json').read_text(encoding='utf-8'))['sessions'][0]
    assert 'audio' not in carried['turns'][1]                        # this machine's files stay
    imported = library.import_bundle(tmp_path / 'b.json')            # Wren exists: a copy
    new_owner = imported['personas'][0]
    assert new_owner != sheet['id']
    [placed] = imported['sessions']
    assert placed['persona_id'] == new_owner
    copy = sessions.get(new_owner, placed['session_id'])
    assert [turn['content'] for turn in copy['turns']] == ['Salut.', 'Ouais bon.']
    assert copy['title'] == 'Les rayonnages' and copy['importedFrom'] == scene['id']
