"""Voice batches, with no model loaded.

The voice worker is replaced by a stub that writes silent takes; what is checked is
everything around it — how a list is read, who speaks each line, how the lines are grouped
and sized, what the folder holds, and that a resumed batch does not pay twice for a line.
The real generation is covered by app/tests/acceptance_batch.py.
"""
import csv
import json
import struct
import sys
import tempfile
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cytools_core import CyToolError                                        # noqa: E402

import tool                                                                 # noqa: E402
from personarp import batches, library                                      # noqa: E402
from personarp.schemas import FORMAT_PERSONA, normalize_persona, normalize_world  # noqa: E402
from personarp.voice import batching, delivery, stable                      # noqa: E402


def _wav(path, seconds=1.0, rate=24000):
    frames = int(seconds * rate)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack('<%dh' % frames, *([0] * frames)))
    return path


# ------------------------------------------------------------------- reading a list

def test_a_script_names_its_speakers_and_continues_lines():
    lines = batches.parse(text='# scène 1\nMaëlis : Je reste.\n  Même seule.\n\nBrannoc: Non.\n'
                               '[soupir] Pas ce soir.\n')
    assert [(line['character'], line['text']) for line in lines] == [
        ('Maëlis', 'Je reste. Même seule.'), ('Brannoc', 'Non. [soupir] Pas ce soir.')]


def test_a_script_must_start_with_a_speaker():
    with pytest.raises(CyToolError):
        batches.parse(text='Une ligne sans personne.\nMaëlis: Oui.')


def test_a_csv_with_a_french_header_and_semicolons(tmp_path):
    path = tmp_path / 'lot.csv'
    path.write_text('personnage;texte;langue;fichier\nMaëlis;"Je reste; même seule.";English;'
                    'intro\nBrannoc;Non.;;\n', encoding='utf-8-sig')
    lines = batches.parse(file=str(path))
    assert lines[0] == {'id': '', 'character': 'Maëlis', 'voice': '',
                        'text': 'Je reste; même seule.', 'language': 'English', 'file': 'intro'}
    assert lines[1]['character'] == 'Brannoc' and lines[1]['language'] == ''


def test_a_csv_without_header_is_speaker_then_text(tmp_path):
    path = tmp_path / 'lot.csv'
    path.write_text('Maëlis,Je reste.\nBrannoc,"Non, pas ce soir."\n', encoding='utf-8')
    lines = batches.parse(file=str(path))
    assert [line['text'] for line in lines] == ['Je reste.', 'Non, pas ce soir.']


def test_a_json_list_or_document(tmp_path):
    rows = [{'personnage': 'Maëlis', 'texte': 'Je reste.'}, {'voice': 'v1', 'text': 'Salut.'},
            {'character': 'X', 'text': ''}]
    listed = tmp_path / 'a.json'
    listed.write_text(json.dumps(rows), encoding='utf-8')
    wrapped = tmp_path / 'b.json'
    wrapped.write_text(json.dumps({'lignes': rows}), encoding='utf-8')
    for path in (listed, wrapped):
        lines = batches.parse(file=str(path))
        assert [line['text'] for line in lines] == ['Je reste.', 'Salut.']   # empty line dropped
        assert lines[1]['voice'] == 'v1'


def test_an_inline_list_is_recognised_whatever_its_format():
    script = 'Maëlis: Je reste, même seule.\nBrannoc: Non.'
    table = 'personnage;texte;langue\nMaëlis;Je reste.;English\n'
    listed = json.dumps([{'character': 'Maëlis', 'text': 'Je reste.'}])
    assert [batches.guess_format(text) for text in (script, table, listed, '# note\n' + table)] \
        == ['script', 'csv', 'json', 'csv']
    assert batches.parse(text=table)[0]['language'] == 'English'
    assert batches.parse(text=listed)[0]['character'] == 'Maëlis'
    assert batches.parse(text=script)[0]['text'] == 'Je reste, même seule.'
    # An explicit format wins: this "CSV" is read as a script.
    assert batches.parse(text='Maëlis: a;b', format='script')[0]['text'] == 'a;b'
    with pytest.raises(CyToolError):
        batches.parse(text='{"lines": 3', format='json')


def test_limits_and_empty_batches_are_refused(tmp_path):
    with pytest.raises(CyToolError):
        batches.parse(text='   ')
    with pytest.raises(CyToolError):
        batches.parse(items=[{'character': 'A', 'text': 'x' * (batches.MAX_TEXT + 1)}])
    with pytest.raises(CyToolError):
        batches.parse(file=str(tmp_path / 'absent.csv'))


def test_file_names_are_numbered_and_never_collide():
    used = set()
    assert batches.file_stem(7, {'speakerId': 'maelis-de-corvanne'}, used) == '0007-maelis-de-corvanne'
    assert batches.file_stem(8, {'file': 'Intro Scène'}, used) == 'Intro-Scene'
    # Windows does not tell Intro-Scene from intro-scene: the second one is renamed.
    assert batches.file_stem(9, {'file': 'intro scene'}, used) == 'intro-scene-2'
    assert batches.file_stem(10, {'givenId': 'SC01_L005'}, used) == 'SC01_L005'
    assert batches.file_stem(11, {'givenId': 'CON'}, used) == '_CON'


# --------------------------------------------------------------- finding the speaker

@pytest.fixture()
def cast(tmp_path, monkeypatch):
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(batches, 'BATCHES', tmp_path / 'batches')
    voices = tmp_path / 'voices'
    voices.mkdir()
    monkeypatch.setattr(stable, 'VOICES', voices)
    monkeypatch.setattr(library, 'VOICES', voices)
    models = {'base': {'backend': 'qwen3tts', 'variant': '1.7B-Base'},
              'custom': {'backend': 'qwen3tts', 'variant': '1.7B-CustomVoice'},
              'design': {'backend': 'qwen3tts', 'variant': '1.7B-VoiceDesign'}}
    monkeypatch.setattr(delivery.catalog, 'catalog', lambda: models)
    monkeypatch.setattr(delivery.catalog, 'installed', lambda key: True)
    monkeypatch.setattr(delivery.catalog, 'directory', lambda key: Path('/models') / key)
    voice = stable.create('Maëlis', _wav(tmp_path / 'fr.wav', 15.0), 'Bonjour.', language='French')
    created = {
        'maelis': personas.create({'name': 'Maëlis de Corvanne', 'aliases': ['La Veuve'],
                                   'voice': {'voice_id': voice['id'], 'language': 'French'}}),
        'brannoc': personas.create({'name': 'Brannoc', 'voice': {
            'description': 'Une voix grave et lente.', 'language': 'French'}}),
        'ilsa': personas.create({'name': 'Ilsa Varn', 'voice': {'speaker': 'Ryan'}}),
        'ilsb': personas.create({'name': 'Ilsa Morrow', 'voice': {'speaker': 'Aiden'}}),
    }
    return {'personas': created, 'voice': voice, 'root': tmp_path}


def test_a_speaker_is_found_by_name_alias_or_a_unique_part(cast):
    finder = batches.Cast()
    for name in ('Maëlis de Corvanne', 'maelis de corvanne', 'la veuve', 'Maëlis', 'Corvanne',
                 'de Corvanne', 'Veuve', cast['personas']['maelis']['id']):
        found, reason = finder.find(name)
        assert found and found['id'] == cast['personas']['maelis']['id'], (name, reason)


def test_an_ambiguous_or_unknown_speaker_is_explained(cast):
    finder = batches.Cast()
    found, reason = finder.find('Ilsa')
    assert found is None and 'Ilsa Varn' in reason and 'Ilsa Morrow' in reason
    found, reason = finder.find('Personne')
    assert found is None and 'Personne' in reason
    found, reason = finder.find('Corv')                    # a word, not a fragment of one
    assert found is None


# ------------------------------------------------------------------ sizing the batches

def test_the_automatic_size_follows_the_free_memory():
    gib = 1024 ** 3
    assert batching.auto_size(None) == batching.CPU_BATCH
    assert batching.auto_size(1 * gib) == 1                        # never zero
    small, large = batching.auto_size(8 * gib), batching.auto_size(32 * gib)
    assert 1 < small < large <= batching.MAX_BATCH


def test_passages_are_pooled_longest_first():
    plans = [('a', [{'text': 'court'}, {'pauseSeconds': 0.4}, {'text': 'beaucoup plus long'}]),
             ('b', [{'text': 'moyen texte'}])]
    pooled = batching.collect(plans)
    assert [(p['line'], p['position']) for p in pooled] == [('a', 2), ('b', 0), ('a', 0)]


class OutOfMemory(RuntimeError):
    pass


def test_a_batch_that_does_not_fit_is_halved_and_the_size_kept():
    seen = []

    def generate(chunk):
        seen.append(len(chunk))
        if len(chunk) > 3:
            raise OutOfMemory('CUDA out of memory')
        return [('wave-%s' % passage['position'], 24000) for passage in chunk]

    passages = [{'line': 'l', 'position': index, 'item': {'text': 'x'}} for index in range(10)]
    results, statistics = batching.generate_all(
        passages, 8, generate, lambda exc: isinstance(exc, OutOfMemory))
    assert seen == [8, 4, 2, 2, 2, 2, 2]
    assert statistics == {'calls': 5, 'retries': 2, 'firstSize': 8, 'size': 2,
                          'sizes': [2, 2, 2, 2, 2]}
    assert results[('l', 9)] == ('wave-9', 24000) and len(results) == 10


def test_the_size_follows_what_a_measured_batch_cost():
    """A small first batch measures; the next ones are sized from it."""
    gib = 1024 ** 3
    seen = []

    def generate(chunk):
        seen.append(len(chunk))
        return [('w', 24000)] * len(chunk)

    def resize(done):
        # 1.3 GB per passage measured, 14 GB of room: 14 * 0.85 // 1.3 = 9 at a time.
        return batching.fit(14 * gib, int(1.3 * gib))

    passages = [{'line': 'l', 'position': index, 'item': {'text': 'x'}} for index in range(30)]
    _, statistics = batching.generate_all(passages, batching.PROBE_BATCH, generate,
                                          lambda exc: False, resize=resize)
    assert seen == [4, 9, 9, 8] and statistics['sizes'] == seen


def test_after_running_out_of_memory_a_measurement_never_grows_the_batch():
    seen = []

    def generate(chunk):
        seen.append(len(chunk))
        if len(chunk) > 3:
            raise OutOfMemory('CUDA out of memory')
        return [('w', 24000)] * len(chunk)

    passages = [{'line': 'l', 'position': index, 'item': {'text': 'x'}} for index in range(9)]
    batching.generate_all(passages, 6, generate, lambda exc: True, resize=lambda done: 12)
    assert seen == [6, 3, 3, 3]


def test_a_measurement_fits_the_room_it_is_given():
    gib = 1024 ** 3
    assert batching.fit(20 * gib, int(1.3 * gib)) == 13
    assert batching.fit(1 * gib, 2 * gib) == 1                       # never zero
    assert batching.fit(500 * gib, gib) == batching.MAX_BATCH


def test_another_error_is_not_retried():
    def generate(chunk):
        raise ValueError('bad text')

    with pytest.raises(ValueError):
        batching.generate_all([{'line': 'l', 'position': 0, 'item': {'text': 'x'}}] * 4, 4,
                              generate, lambda exc: False)


def test_running_out_of_memory_with_one_passage_is_an_error():
    def generate(chunk):
        raise OutOfMemory('CUDA out of memory')

    with pytest.raises(OutOfMemory):
        batching.generate_all([{'line': 'l', 'position': 0, 'item': {'text': 'x'}}], 4,
                              generate, lambda exc: True)


# --------------------------------------------------------------- the operation, end to end

class FakeWorker:
    """Writes one silent take per item, like the worker, and remembers the requests."""

    def __init__(self, fail_texts=()):
        self.requests = []
        self.fail_texts = set(fail_texts)

    def __call__(self, context, parameters, offset=0.0, scale=1.0):
        self.requests.append(parameters)
        out = Path(parameters['workspace']) / parameters['output_dir']
        out.mkdir(parents=True, exist_ok=True)
        items = []
        for item in parameters['items']:
            if item['text'] in self.fail_texts:
                items.append({'id': item['id'], 'error': 'The model refused.'})
                continue
            path = _wav(out / (item['file'] + '.wav'))
            items.append({'id': item['id'], 'error': '', 'file': str(path),
                          'durationSeconds': 1.0, 'sampleRate': 24000, 'passages': 1})
        return {'items': items, 'mode': parameters['mode'], 'model': parameters['model'],
                'batchSize': 4, 'firstBatchSize': 4, 'calls': 1, 'memoryRetries': 0,
                'passages': len(items), 'generationSeconds': 0.1, 'freeVramBytes': None}


def _run(runtime, operation, parameters, permissions=('filesystemExternal',)):
    actor = runtime.authenticate(runtime.create_client('Test', list(permissions))['token'])
    session = runtime.create_session(actor, temporary=True)['sessionId']
    job = runtime.submit(actor, session, operation, parameters)
    return runtime.wait(actor, job['jobId'], timeout=60)


SCRIPT = ('Maëlis: Je reste.\n'
          'Brannoc: [ton: grave] Alors je reste aussi.\n'
          'Personne: Qui parle ?\n'
          'Ilsa: Laquelle de nous deux ?\n'
          'La Veuve: Toi. [pause: 400ms] Viens.\n')


def test_a_batch_makes_a_folder_with_its_source_its_takes_and_its_results(cast, monkeypatch):
    worker = FakeWorker()
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', worker)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch', {'text': SCRIPT, 'name': 'Acte I',
                                               'batch_size': 6})
    assert result['state'] == 'Completed', result.get('error')
    outputs = result['outputs']
    assert outputs['lines'] == 5 and outputs['done'] == 3 and outputs['failed'] == 2
    folder = Path(outputs['folder'])
    assert folder.parent == cast['root'] / 'batches' and folder.name.startswith('acte-i-')
    assert (folder / 'source.txt').read_text(encoding='utf-8') == SCRIPT
    lot = json.loads((folder / 'lot.json').read_text(encoding='utf-8'))
    assert [line['speakerId'] for line in lot['lines']] == [
        cast['personas']['maelis']['id'], cast['personas']['brannoc']['id'], '', '',
        cast['personas']['maelis']['id']]

    # One request per set of weights: the stable voice is a clone, Brannoc is invented.
    modes = sorted((request['mode'], len(request['items'])) for request in worker.requests)
    assert modes == [('clone', 2), ('design', 1)]
    assert all(request['batch_size'] == 6 for request in worker.requests)
    clone = next(request for request in worker.requests if request['mode'] == 'clone')
    assert {item['reference_audio'] for item in clone['items']} == {cast['voice']['reference_audio']}

    takes = sorted(path.name for path in (folder / 'voix').iterdir())
    assert takes == ['0001-%s.wav' % cast['personas']['maelis']['id'],
                     '0002-%s.wav' % cast['personas']['brannoc']['id'],
                     '0005-%s.wav' % cast['personas']['maelis']['id']]
    results = json.loads((folder / 'resultats.json').read_text(encoding='utf-8'))
    by_index = {line['index']: line for line in results['lines']}
    assert by_index[1]['status'] == 'ok' and by_index[1]['file'] == 'voix/' + takes[0]
    assert 'Personne' in by_index[3]['error'] and 'Ilsa Varn' in by_index[4]['error']
    assert results['summary']['done'] == 3 and results['summary']['failed'] == 2
    with open(folder / 'resultats.csv', encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.reader(handle, delimiter=';'))
    assert rows[0][:4] == ['index', 'id', 'status', 'character'] and len(rows) == 6


def test_a_resumed_batch_only_speaks_what_is_missing(cast, monkeypatch):
    worker = FakeWorker(fail_texts={'Alors je reste aussi.', '[ton: grave] Alors je reste aussi.'})
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', worker)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        first = _run(runtime, 'speak_batch', {'text': SCRIPT})['outputs']
        assert first['done'] == 2 and first['failed'] == 3
        # The missing character now exists; the refused line is tried again.
        library.personas.create({'name': 'Personne', 'voice': {'speaker': 'Ryan'}})
        worker.requests.clear()
        worker.fail_texts.clear()
        second = _run(runtime, 'speak_batch', {'resume': first['batch']})
    assert second['state'] == 'Completed', second.get('error')
    outputs = second['outputs']
    assert outputs['batch'] == first['batch'] and outputs['skipped'] == 2
    assert outputs['done'] == 4 and outputs['failed'] == 1          # Ilsa is still ambiguous
    spoken = sorted(item['file'] for request in worker.requests for item in request['items'])
    assert spoken == ['0002-%s' % cast['personas']['brannoc']['id'], '0003-personne']


def test_a_stable_voice_can_speak_a_line_without_a_character(cast, monkeypatch):
    worker = FakeWorker()
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', worker)
    items = [{'voice': cast['voice']['id'], 'text': 'Bonjour à tous.', 'file': 'annonce'},
             {'voice': 'absente', 'text': 'Rien.'},
             {'character': 'Brannoc', 'voice': cast['voice']['id'], 'text': 'Emprunt.',
              'language': 'English'}]
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch', {'items': items, 'language': 'German'})
    outputs = result['outputs']
    assert result['state'] == 'Completed' and outputs['done'] == 2 and outputs['failed'] == 1
    folder = Path(outputs['folder'])
    assert (folder / 'voix' / 'annonce.wav').is_file() and (folder / 'source.json').is_file()
    lines = json.loads((folder / 'resultats.json').read_text(encoding='utf-8'))['lines']
    assert lines[0]['languageUsed'] == 'German'                   # the batch default
    assert lines[0]['speakerName'] == cast['voice']['name'] and lines[0]['speakerId'] == ''
    assert lines[2]['languageUsed'] == 'English'                  # the line's own
    assert lines[2]['speakerId'] == cast['personas']['brannoc']['id']
    assert lines[2]['mode'] == 'clone'                            # the voice given wins
    assert 'absente' in lines[1]['error']


def test_a_failed_group_does_not_stop_the_others(cast, monkeypatch):
    def worker(context, parameters, offset=0.0, scale=1.0):
        if parameters['mode'] == 'design':
            raise CyToolError('WorkerFailed', 'The design model is broken.')
        return FakeWorker()(context, parameters)
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', worker)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch', {'text': 'Maëlis: Oui.\nBrannoc: Non.'})
    outputs = result['outputs']
    assert result['state'] == 'Completed' and outputs['done'] == 1 and outputs['failed'] == 1
    assert 'design model is broken' in outputs['errors'][0]['error']


def test_batches_are_listed_with_their_progress(cast, monkeypatch):
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', FakeWorker())
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        _run(runtime, 'speak_batch', {'text': 'Maëlis: Oui.\nPersonne: Non.', 'name': 'essai'})
        listed = _run(runtime, 'list_batches', {})['outputs']['batches']
    assert len(listed) == 1 and listed[0]['name'] == 'essai'
    assert listed[0]['lines'] == 2 and listed[0]['done'] == 1 and not listed[0]['complete']


def test_a_dry_run_explains_every_line_and_generates_nothing(cast, monkeypatch):
    worker = FakeWorker()
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', worker)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch', {'text': SCRIPT, 'dry_run': True,
                                               'language': 'English'})
    outputs = result['outputs']
    assert result['state'] == 'Completed', result.get('error')
    assert worker.requests == [] and not (cast['root'] / 'batches').exists()
    assert not result['resourceEstimate'].get('vramBytes')        # a check never waits for the GPU
    assert outputs['dryRun'] and outputs['lines'] == 5
    assert outputs['ready'] == 3 and outputs['failed'] == 2
    first = outputs['preview'][0]
    assert first['speakerName'] == 'Maëlis de Corvanne' and first['mode'] == 'clone'
    assert first['voiceUsed'] == cast['voice']['id'] and first['languageUsed'] == 'English'
    assert sorted((group['mode'], group['lines']) for group in outputs['groups']) == [
        ('clone', 2), ('design', 1)]


def test_an_ai_client_sends_its_list_inline_without_any_permission(cast, monkeypatch):
    """The ordinary MCP client has no permission: the inline list must be enough."""
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', FakeWorker())
    table = 'personnage;texte\nMaëlis;Je reste.\nBrannoc;Non.\n'
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch', {'text': table}, permissions=())
    assert result['state'] == 'Completed', result.get('error')
    assert result['outputs']['done'] == 2
    assert (Path(result['outputs']['folder']) / 'source.csv').read_text(encoding='utf-8') == table


def test_a_batch_file_needs_the_permission_and_is_kept_in_the_folder(cast, monkeypatch,
                                                                     tmp_path):
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', FakeWorker())
    source = tmp_path / 'dossier à part' / 'Acte II.csv'
    source.parent.mkdir()
    source.write_text('character,text,file\nMaëlis,Je reste.,ouverture\n', encoding='utf-8')
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        with pytest.raises(CyToolError) as refused:
            _run(runtime, 'speak_batch_file', {'file': str(source)}, permissions=())
        assert refused.value.code == 'AccessDenied'
        result = _run(runtime, 'speak_batch_file', {'file': str(source)})
    assert result['state'] == 'Completed', result.get('error')
    folder = Path(result['outputs']['folder'])
    assert (folder / 'source.csv').read_text(encoding='utf-8') == source.read_text(encoding='utf-8')
    assert (folder / 'voix' / 'ouverture.wav').is_file()
    assert folder.name.startswith('acte-ii-'), folder.name     # named after the file
    assert source.is_file()                                       # the original is untouched


EXAMPLE_BATCHES = sorted((Path(tool.__file__).parent / 'examples' / 'lots').glob('*.*'))


@pytest.mark.parametrize('path', EXAMPLE_BATCHES, ids=lambda path: path.name)
def test_every_example_batch_is_spoken_whole_by_the_valdrenn_cast(path, tmp_path, monkeypatch):
    """The shipped example lists must work as soon as the Valdrenn example is imported."""
    from personarp import examples
    personas = library.Collection(tmp_path / 'personas', normalize_persona, FORMAT_PERSONA, 'persona')
    worlds = library.Collection(tmp_path / 'worlds', normalize_world, 'cytools-personarp-world', 'world')
    monkeypatch.setattr(library, 'personas', personas)
    monkeypatch.setattr(library, 'worlds', worlds)
    monkeypatch.setattr(library, 'VOICES', tmp_path / 'voices')
    monkeypatch.setattr(stable, 'VOICES', tmp_path / 'voices')
    monkeypatch.setattr(batches, 'BATCHES', tmp_path / 'batches')
    library.import_bundle(next(bundle for bundle in examples.bundles() if 'valdrenn' in bundle.name))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch_file', {'file': str(path), 'dry_run': True})
    outputs = result['outputs']
    assert result['state'] == 'Completed', result.get('error')
    assert outputs['failed'] == 0, [line['error'] for line in outputs['preview'] if line['error']]
    assert outputs['ready'] == outputs['lines'] >= 3


def test_an_unknown_batch_cannot_be_resumed(cast):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch', {'resume': '../../etc'})
    assert result['state'] == 'Failed'


# ------------------------------------------------------------------------ line ids

def test_a_script_line_can_carry_its_id():
    lines = batches.parse(text='SC01_L01 | Maëlis: Je reste.\nBrannoc: Non.\n  Jamais.')
    assert [(line['id'], line['character'], line['text']) for line in lines] == [
        ('SC01_L01', 'Maëlis', 'Je reste.'), ('', 'Brannoc', 'Non. Jamais.')]
    with pytest.raises(CyToolError):
        batches.parse(text='SC01 | pas de nom ici')


def test_every_line_gets_an_id_and_a_duplicate_is_refused():
    lines = [{'id': '0002'}, {'id': ''}, {'id': 'a'}, {'id': 'A'}]
    duplicates = batches.assign_ids(lines)
    assert [line['id'] for line in lines] == ['0002', '0002-2', 'a', 'A']
    assert duplicates == {3: 'Id already used by another line: A (line 3)'}


def test_takes_are_named_after_their_ids(cast, monkeypatch):
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', FakeWorker())
    items = [{'id': 'SC01_L01', 'character': 'Maëlis', 'text': 'Oui.'},
             {'character': 'Brannoc', 'text': 'Non.'},
             {'id': 'sc01_l01', 'character': 'Brannoc', 'text': 'Doublon.'}]
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        outputs = _run(runtime, 'speak_batch', {'items': items})['outputs']
    folder = Path(outputs['folder'])
    lines = json.loads((folder / 'resultats.json').read_text(encoding='utf-8'))['lines']
    assert [(line['id'], line['status']) for line in lines] == [
        ('SC01_L01', 'ok'), ('0002', 'ok'), ('sc01_l01', 'error')]
    assert lines[0]['file'] == 'voix/SC01_L01.wav' and (folder / lines[0]['file']).is_file()
    assert lines[1]['file'].startswith('voix/0002-')
    assert outputs['errors'] == [{'index': 3, 'id': 'sc01_l01',
                                  'error': 'Id already used by another line: sc01_l01 (line 1)'}]


# ------------------------------------------------------------- a task's own characters

def _export_with_english_voice(cast):
    """Maëlis with an English stable voice of her own, exported with the recordings."""
    english = stable.create('Maëlis EN', _wav(cast['root'] / 'en.wav', 15.0), 'Hello.',
                            language='English')
    maelis = library.personas.get(cast['personas']['maelis']['id'])
    maelis['voice']['languages'] = [{'language': 'English', 'source': 'voice',
                                     'voice_id': english['id']}]
    library.personas.save(maelis)
    exported = library.export_bundle([maelis['id'], cast['personas']['brannoc']['id']],
                                     destination=str(cast['root'] / 'paquet.zip'),
                                     include_audio=True)
    return exported, english


def test_an_export_carries_the_voices_of_every_language(cast):
    exported, english = _export_with_english_voice(cast)
    assert sorted(exported['voices']) == sorted([cast['voice']['id'], english['id']])
    assert exported['bundledAudio'] == 2


def _empty_library(cast, monkeypatch):
    """Point the library at an empty folder, as on the machine that runs the task."""
    other = cast['root'] / 'autre-machine'
    monkeypatch.setattr(library, 'personas', library.Collection(
        other / 'personas', normalize_persona, FORMAT_PERSONA, 'persona'))
    monkeypatch.setattr(library, 'worlds', library.Collection(
        other / 'worlds', normalize_world, 'cytools-personarp-world', 'world'))
    (other / 'voices').mkdir(parents=True)
    monkeypatch.setattr(library, 'VOICES', other / 'voices')
    monkeypatch.setattr(stable, 'VOICES', other / 'voices')
    return other


def test_a_task_brings_complete_characters_and_leaves_the_library_alone(cast, monkeypatch):
    exported, english = _export_with_english_voice(cast)
    other = _empty_library(cast, monkeypatch)
    worker = FakeWorker()
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', worker)
    table = ('id;personnage;texte;langue\n'
             'A1;Maëlis;Je reste.;\n'
             'A2;Maëlis;I am staying.;English\n'
             'A3;Brannoc;We cross the river.;English\n')
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        result = _run(runtime, 'speak_batch_file', {
            'text': table, 'personas': [exported['file']], 'use_library': False})
    assert result['state'] == 'Completed', result.get('error')
    outputs = result['outputs']
    assert outputs['done'] == 3 and outputs['problems'] == []
    assert sorted(item['name'] for item in outputs['personas']) == [
        'Brannoc', 'Maëlis de Corvanne']
    folder = Path(outputs['folder'])
    task = folder / 'personnages'
    assert sorted(path.name for path in (task / 'fiches').glob('*.json')) == sorted(
        [cast['personas']['maelis']['id'] + '.json', cast['personas']['brannoc']['id'] + '.json'])
    assert len(list((task / 'voix-stables').glob('*.wav'))) == 2
    # Nothing reached the library of the machine that ran the task.
    assert library.personas.list() == [] and list((other / 'voices').iterdir()) == []

    lines = {line['id']: line for line in json.loads(
        (folder / 'resultats.json').read_text(encoding='utf-8'))['lines']}
    assert {line['speakerSource'] for line in lines.values()} == {'task'}
    assert lines['A1']['voiceUsed'] == cast['voice']['id']            # her own voice
    assert lines['A2']['voiceUsed'] == english['id']                  # her English voice
    assert lines['A3']['mode'] == 'design'                            # Brannoc has no stable voice
    spoken = {item['file']: item for request in worker.requests for item in request['items']}
    assert Path(spoken['A2']['reference_audio']).parent == task / 'voix-stables'
    assert (folder / 'voix' / 'A2.wav').is_file()


def test_a_resumed_task_still_speaks_with_its_own_characters(cast, monkeypatch):
    exported, _ = _export_with_english_voice(cast)
    _empty_library(cast, monkeypatch)
    worker = FakeWorker(fail_texts={'Non.'})
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', worker)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        first = _run(runtime, 'speak_batch_file', {
            'text': 'Maëlis: Oui.\nBrannoc: Non.', 'personas': [exported['file']]})['outputs']
        worker.fail_texts.clear()
        worker.requests.clear()
        second = _run(runtime, 'speak_batch', {'resume': first['batch']}, permissions=())
    assert second['state'] == 'Completed', second.get('error')
    assert second['outputs']['skipped'] == 1 and second['outputs']['done'] == 2
    assert [item['file'] for request in worker.requests for item in request['items']] == [
        '0002-' + cast['personas']['brannoc']['id']]


def test_the_task_characters_come_before_the_library(cast, monkeypatch):
    exported, _ = _export_with_english_voice(cast)
    library.personas.create({'name': 'Maëlis', 'voice': {'speaker': 'Aiden'}})   # a namesake
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', FakeWorker())
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        outputs = _run(runtime, 'speak_batch_file', {
            'text': 'Maëlis: Oui.\nIlsa Varn: Moi aussi.', 'personas': [exported['file']],
            'dry_run': True})['outputs']
    first, second = outputs['preview']
    assert first['speakerSource'] == 'task' and first['mode'] == 'clone'
    assert second['speakerSource'] == 'library'                       # not in the task


def test_a_recording_that_does_not_match_its_fingerprint_is_refused(cast, monkeypatch):
    import zipfile
    exported, english = _export_with_english_voice(cast)
    tampered = cast['root'] / 'altere.zip'
    with zipfile.ZipFile(exported['file']) as source, zipfile.ZipFile(tampered, 'w') as target:
        for name in source.namelist():
            payload = source.read(name)
            if name.endswith('.wav') and english['id'] in name:
                payload = payload[:-100] + b'\x01' * 100      # silence made audible
            target.writestr(name, payload)
    _empty_library(cast, monkeypatch)
    monkeypatch.setattr(tool.voice_runner, 'speak_batch', FakeWorker())
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        outputs = _run(runtime, 'speak_batch_file', {
            'text': 'Maëlis: Hello.', 'language': 'English', 'personas': [str(tampered)],
            'dry_run': True})['outputs']
    assert any('fingerprint' in problem for problem in outputs['problems'])
    line = outputs['preview'][0]
    assert line['voiceUsed'] == cast['voice']['id']                   # never the altered voice
    assert "own voice was used" in line['note']


def test_characters_from_files_need_the_permission(cast, monkeypatch):
    exported, _ = _export_with_english_voice(cast)
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        with pytest.raises(CyToolError) as refused:
            _run(runtime, 'speak_batch_file', {'text': 'Maëlis: Oui.',
                                               'personas': [exported['file']]}, permissions=())
    assert refused.value.code == 'AccessDenied'
