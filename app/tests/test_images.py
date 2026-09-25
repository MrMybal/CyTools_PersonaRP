"""Reference photographs: attaching, verifying, and the vision request that reads them.

The vision model itself is exercised by app/tests/acceptance_vision.py, which loads weights.
"""
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cytools_core import CyToolError                                        # noqa: E402

from personarp import authoring, imaging, library                           # noqa: E402
from personarp.schemas import (FORMAT_PERSONA, normalize_persona,           # noqa: E402
                               normalize_world)


def _picture(path, size=(64, 48), colour=(30, 40, 90)):
    from PIL import Image
    Image.new('RGB', size, colour).save(path)
    return path


@pytest.fixture()
def sheets(tmp_path, monkeypatch):
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA,
                                  'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world,
                                'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(library, 'EXPORTS', tmp_path / 'exports')
    monkeypatch.setattr(library, 'VOICES', tmp_path / 'voices')
    monkeypatch.setattr(imaging, 'PERSONAS', tmp_path / 'personas')
    return tmp_path


# ------------------------------------------------------------------------ probing

def test_probe_reports_the_real_pixel_size(tmp_path):
    details = imaging.probe(_picture(tmp_path / 'a.png', (120, 80)))
    assert (details['width'], details['height']) == (120, 80)
    assert details['mimeType'] == 'image/png'


def test_a_non_image_extension_is_refused(tmp_path):
    target = tmp_path / 'notes.txt'
    target.write_text('not an image', encoding='utf-8')
    with pytest.raises(CyToolError) as failure:
        imaging.probe(target)
    assert 'Unsupported image type' in str(failure.value)


def test_a_file_that_is_not_really_an_image_is_refused(tmp_path):
    target = tmp_path / 'fake.png'
    target.write_bytes(b'this is not a PNG')
    with pytest.raises(CyToolError):
        imaging.probe(target)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(CyToolError):
        imaging.probe(tmp_path / 'absent.png')


def test_an_oversized_file_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(imaging, 'MAX_BYTES', 10)
    with pytest.raises(CyToolError) as failure:
        imaging.probe(_picture(tmp_path / 'big.png', (64, 64)))
    assert 'under' in str(failure.value)


# ------------------------------------------------------------------------ attaching

def test_adding_copies_the_picture_beside_the_sheet(sheets, tmp_path):
    persona = library.personas.create({'name': 'Nymphaea'})
    source = _picture(tmp_path / 'portrait.png', (200, 300))
    persona = imaging.add(persona, source, 'portrait', 'sur le pont')
    reference = persona['references'][0]
    stored = Path(reference['file'])
    assert stored.is_file() and stored.parent == imaging.folder('nymphaea')
    assert stored != source, 'the original must not be moved'
    assert reference['role'] == 'portrait' and reference['caption'] == 'sur le pont'
    assert (reference['width'], reference['height']) == (200, 300)
    assert len(reference['sha256']) == 64


def test_two_pictures_of_the_same_name_do_not_overwrite(sheets, tmp_path):
    persona = library.personas.create({'name': 'Nymphaea'})
    first = _picture(tmp_path / 'a' / 'photo.png', (10, 10)) if (tmp_path / 'a').mkdir(
        parents=True, exist_ok=True) is None else None
    second = _picture(tmp_path / 'b' / 'photo.png', (20, 20)) if (tmp_path / 'b').mkdir(
        parents=True, exist_ok=True) is None else None
    persona = imaging.add(persona, first, 'portrait')
    persona = imaging.add(persona, second, 'outfit')
    files = [Path(item['file']).name for item in persona['references']]
    assert len(set(files)) == 2, files


def test_the_number_of_pictures_is_bounded(sheets, tmp_path, monkeypatch):
    monkeypatch.setattr(imaging, 'MAX_PER_PERSONA', 2)
    persona = library.personas.create({'name': 'Nymphaea'})
    for index in range(2):
        persona = imaging.add(persona, _picture(tmp_path / ('p%d.png' % index)), 'reference')
    with pytest.raises(CyToolError):
        imaging.add(persona, _picture(tmp_path / 'extra.png'), 'reference')


def test_removing_moves_the_picture_to_trash(sheets, tmp_path):
    persona = library.personas.create({'name': 'Nymphaea'})
    persona = imaging.add(persona, _picture(tmp_path / 'portrait.png'), 'portrait')
    stored = persona['references'][0]['file']
    persona, moved = imaging.remove(persona, stored)
    assert persona['references'] == []
    assert not Path(stored).exists()
    assert Path(moved).is_file(), 'the picture is kept, not deleted'


def test_removing_an_unknown_picture_is_refused(sheets):
    persona = library.personas.create({'name': 'Nymphaea'})
    with pytest.raises(CyToolError):
        imaging.remove(persona, 'nowhere.png')


def test_verify_notices_a_missing_or_changed_picture(sheets, tmp_path):
    persona = library.personas.create({'name': 'Nymphaea'})
    persona = imaging.add(persona, _picture(tmp_path / 'a.png'), 'portrait')
    persona = imaging.add(persona, _picture(tmp_path / 'b.png'), 'outfit')
    assert all(item['ok'] for item in imaging.verify(persona))

    _picture(Path(persona['references'][0]['file']), (99, 99), (200, 10, 10))
    Path(persona['references'][1]['file']).unlink()
    report = imaging.verify(persona)
    assert report[0]['reason'] == 'changed since it was added'
    assert report[1]['reason'] == 'missing'


# ------------------------------------------------------------------------ encoding

def test_a_large_picture_is_downscaled_before_it_is_sent(tmp_path):
    encoded = imaging.encoded(_picture(tmp_path / 'huge.png', (4000, 3000)), long_edge=1024)
    assert encoded['sentWidth'] == 1024 and encoded['sentHeight'] == 768
    assert encoded['url'].startswith('data:image/jpeg;base64,')


def test_a_small_picture_is_sent_as_it_is(tmp_path):
    encoded = imaging.encoded(_picture(tmp_path / 'small.png', (320, 240)), long_edge=1024)
    assert (encoded['sentWidth'], encoded['sentHeight']) == (320, 240)


# ------------------------------------------------------------------ vision request

def test_the_vision_schema_is_constrainable():
    schema = authoring.vision_schema()
    assert schema['additionalProperties'] is False
    assert set(schema['properties']) == set(authoring.VISION_FIELDS)
    assert schema['properties']['visual_tags']['type'] == 'array'
    for name, spec in schema['properties'].items():
        assert isinstance(spec['type'], str), (name, 'unions do not compile to a grammar')


def test_the_vision_request_carries_the_role_and_the_caption():
    request = authoring.vision_request('full_body', 'sur le pont', 'Francais')
    assert 'full body' in request and 'sur le pont' in request and 'Francais' in request


def test_the_vision_request_can_show_what_the_sheet_already_says():
    request = authoring.vision_request(existing={'hair': 'noirs'})
    assert 'noirs' in request and 'correct the rest' in request


def test_the_vision_prompt_forbids_inventing_a_history():
    assert 'Report only what is visible' in authoring.VISION_SYSTEM
    assert 'do not guess a name' in authoring.VISION_SYSTEM.lower()


def test_a_vision_proposal_merges_into_the_appearance_only():
    persona = normalize_persona({'name': 'Nymphaea', 'memory': {'facts': ['garde moi']}})
    merged = authoring.apply_proposal(persona, {'hair': 'noirs', 'visual_tags': ['stylet']},
                                      'appearance')
    assert merged['appearance']['hair'] == 'noirs'
    assert merged['appearance']['visual_tags'] == ['stylet']
    assert merged['memory']['facts'] == ['garde moi']


# -------------------------------------------------------------------- export

def test_photographs_travel_with_an_export(sheets, tmp_path):
    persona = library.personas.create({'name': 'Nymphaea'})
    persona = imaging.add(persona, _picture(tmp_path / 'portrait.png', (64, 64)), 'portrait',
                          'sur le pont')
    library.personas.save(persona)

    exported = library.export_bundle(['nymphaea'])
    assert exported['bundledImages'] == 1
    assert exported['file'].endswith('.zip')
    with zipfile.ZipFile(exported['file']) as archive:
        names = archive.namelist()
        bundle = json.loads(archive.read('persona-bundle.json'))
    assert any(name.startswith('images/nymphaea/') for name in names)
    assert bundle['personas'][0]['references'][0]['file'].startswith('images/nymphaea/')

    # Re-importing must put the picture back on disk next to the new sheet.
    library.personas.remove('nymphaea')
    imported = library.import_bundle(exported['file'])
    restored = library.personas.get(imported['personas'][0])
    reference = restored['references'][0]
    assert Path(reference['file']).is_file()
    assert reference['caption'] == 'sur le pont' and reference['role'] == 'portrait'


def test_an_export_without_photographs_stays_a_plain_document(sheets):
    library.personas.create({'name': 'Nymphaea'})
    exported = library.export_bundle(['nymphaea'])
    assert exported['bundledImages'] == 0 and exported['file'].endswith('.json')


def test_a_visual_tag_cannot_be_a_single_short_word():
    """Single words like "femme" or "bleue" identify nobody in an image prompt, so the
    grammar itself refuses them."""
    tags = authoring.vision_schema()['properties']['visual_tags']
    assert tags['items']['minLength'] >= 6
    assert 6 <= tags['minItems'] and tags['maxItems'] <= 12


def test_the_vision_request_shows_a_form_example_and_a_counter_example():
    request = authoring.vision_request()
    assert 'Example of the FORM only' in request
    assert 'Wrong, whoever is in the picture:' in request


def test_every_field_is_asked_but_only_the_visible_ones_need_words():
    """Optional fields were skipped although the observation described them; required and
    allowed empty, each is answered, and one the picture cannot show stays empty."""
    schema = authoring.vision_schema()
    assert set(schema['required']) == set(authoring.VISION_FIELDS)
    for field in ('build', 'marks', 'style_reference', 'face', 'skin', 'accessories'):
        assert 'minLength' not in schema['properties'][field], field


def test_a_generic_tag_no_longer_passes():
    tags = authoring.vision_schema()['properties']['visual_tags']
    assert len('jeune femme') < tags['items']['minLength'] <= len('sacoche en cuir fauve')
    request = authoring.vision_request()
    assert '"jeune femme", "yeux bleus"' in request


def test_the_request_forbids_repeating_the_same_words_across_fields():
    request = authoring.vision_request()
    assert 'leave that field as an empty string' in request
    assert 'Never repeat the same words in two different fields' in request
    assert 'Answer every field' in request


def test_the_tag_example_cannot_pass_for_an_answer():
    """An example that looks like a plausible answer gets copied verbatim; this one is
    about a different person in a different register."""
    request = authoring.vision_request()
    assert 'never reuse these words' in request
    assert 'FORM only' in request


# ------------------------------------------------------------- two passes: look, then write

def test_the_main_fields_must_be_phrases():
    """One pass constrained to JSON answered one word per field ("longue", "bleus"); the
    writing pass now needs phrases for what a portrait always shows."""
    properties = authoring.vision_schema()['properties']
    assert properties['summary']['minLength'] >= 40
    assert properties['outfit']['minLength'] >= 20
    assert properties['hair']['minLength'] >= 12 and properties['eyes']['minLength'] >= 8
    assert 'minLength' not in properties['build'], 'a portrait cannot always answer that'


def test_the_look_pass_asks_for_detailed_prose():
    request = authoring.observation_request('full_body', 'sur le pont')
    assert '150 to 300 words' in request and 'garment by garment' in request
    assert 'full body' in request and 'sur le pont' in request
    assert 'JSON' not in request and 'JSON' not in authoring.VISION_SYSTEM


def test_the_write_pass_works_from_the_observation():
    request = authoring.vision_request(language='Francais', observation='Long charcoal hair.')
    assert 'Long charcoal hair.' in request
    for field in ('summary', 'outfit', 'accessories', 'style_reference'):
        assert '- %s:' % field in request
    assert 'Write the values in: Francais' in request


def test_a_photograph_is_read_in_two_passes(tmp_path, monkeypatch):
    """Look with the picture and no grammar; then write, text only, under the schema — on
    the model already loaded."""
    import tempfile
    import tool
    calls = []

    def fake_generate(self, context, settings, items, json_schema=None, progress=(5, 15),
                      fit=True):
        calls.append({'settings': settings, 'items': items, 'schema': json_schema})
        if json_schema is None:
            return {'text': 'A young woman with long charcoal hair worn half up.',
                    'seconds': 2.0, 'reused': False}
        return {'text': json.dumps({
            'summary': 'Jeune femme aux longs cheveux anthracite, regard clair et calme',
            'hair': 'longs cheveux anthracite, raides, a demi releves',
            'eyes': 'yeux bleu-gris, en amande', 'outfit': 'tunique bleu nuit brodee d etoiles',
            'build': '',
            'visual_tags': ['cheveux anthracite a demi releves', 'tunique bleu nuit etoilee',
                            'sacoche de cuir fauve', 'boucles d oreilles en fil d or',
                            'yeux bleu-gris en amande', 'teint pale et lisse']}),
            'seconds': 1.5, 'reused': True}

    monkeypatch.setattr(tool.ResidentModel, 'generate', fake_generate)
    monkeypatch.setattr(tool.models, 'vision_models', lambda *a, **k: ['qwen25-vl-7b'])
    monkeypatch.setattr(tool.models, 'is_vision', lambda model: True)
    picture = _picture(tmp_path / 'portrait.png', (64, 96))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        actor = runtime.authenticate(runtime.create_client('T', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        job = runtime.submit(actor, session, 'describe_image',
                             {'image': str(picture), 'language': 'Francais'})
        job = runtime.wait(actor, job['jobId'], timeout=60)
    assert job['state'] == 'Completed', job.get('error')
    outputs = job['outputs']

    look, write = calls
    assert look['schema'] is None and look['settings']['keep_loaded'] is True
    assert any(part.get('type') == 'image_url' for part in look['items'][1]['content'])
    assert write['schema'] == authoring.vision_schema()
    assert isinstance(write['items'][1]['content'], str)                    # text only
    assert 'long charcoal hair worn half up' in write['items'][1]['content']
    assert write['settings']['llm_model'] == look['settings']['llm_model'] == 'qwen25-vl-7b'

    assert outputs['observation'].startswith('A young woman')
    assert outputs['proposal']['hair'].startswith('longs cheveux')
    assert 'build' not in outputs['proposal']                              # empty dropped
    assert len(outputs['proposal']['visual_tags']) == 6
    assert outputs['seconds'] == 3.5


def test_a_foreign_script_slipped_into_a_french_sheet_is_removed():
    cleaned = authoring.clean_vision_fields({
        'skin': 'teint clair, texture lisse sans taches ou雀斑',
        'visual_tags': ['sacoche en cuir fauve', '雀斑'], 'hair': 'longs cheveux bruns'},
        'Francais')
    assert cleaned['skin'] == 'teint clair, texture lisse sans taches'
    assert cleaned['visual_tags'] == ['sacoche en cuir fauve']
    assert cleaned['hair'] == 'longs cheveux bruns'
    kept = authoring.clean_vision_fields({'hair': '黒い長い髪'}, 'Japanese')
    assert kept['hair'] == '黒い長い髪'


def test_the_write_pass_keeps_one_language_and_one_thing_per_tag():
    request = authoring.vision_request(language='Francais')
    assert 'not one word of another language' in request
    assert 'never two tags about the same garment or feature' in request


def test_a_stuttered_word_and_a_repeated_tag_are_cleaned():
    cleaned = authoring.clean_vision_fields({
        'face': 'un menton fort fort et des pommettes hautes',
        'visual_tags': ['menton fort fort', 'Sac en cuir marron', 'sac en cuir marron']})
    assert cleaned['face'] == 'un menton fort et des pommettes hautes'
    assert cleaned['visual_tags'] == ['menton fort', 'Sac en cuir marron']
    # A French reflexive is not a stutter.
    assert authoring.clean_vision_fields({'hair': 'nous nous coiffons'})['hair'] \
        == 'nous nous coiffons'
