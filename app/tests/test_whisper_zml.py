"""PersonaRP Whisper ZML integration tests with a fixture launcher and real job handling."""
import json
from pathlib import Path
import sys
import time
import wave

import psutil
import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import tool
from personarp import locks
from personarp.voice import catalog, runner, stable


LAUNCHER = """
import json
import os
from pathlib import Path
import sys
import time

args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
assert Path(args['--runtime-config']).is_file()
assert Path(args['--workspace']).name.startswith('whisper-zml-')
assert Path(args['--audio']).is_file()
assert args['--language'] == 'auto'
marker = os.environ.get('PERSONARP_TEST_LAUNCHER_PID')
if marker:
    Path(marker).write_text(str(os.getpid()), encoding='ascii')
    time.sleep(60)
print(json.dumps({'text': 'Bonjour.', 'segments': [{'start': 0, 'end': 1, 'text': 'Bonjour.'}],
                  'duration': 5, 'language': 'fr', 'complete': True,
                  'placement': {'backend': 'cpu', 'pjrt': 'cpu', 'device': 'cpu:0', 'shards': 1}}))
"""


@pytest.fixture
def transcription(monkeypatch, tmp_path):
    launcher = tmp_path / 'launcher.py'
    launcher.write_text(LAUNCHER, encoding='utf-8')
    config = tmp_path / 'runtime.json'
    config.write_text(json.dumps({'launcher': str(launcher)}), encoding='utf-8')
    model_dir = tmp_path / 'model'
    model_dir.mkdir()
    audio = tmp_path / 'prise de voix.wav'
    with wave.open(str(audio), 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(bytes(160000))
    monkeypatch.setenv('CYTOOLS_WHISPER_ZML_CONFIG', str(config))
    monkeypatch.setattr(catalog, 'engine_python', lambda: Path(sys.executable))
    monkeypatch.setattr(catalog, 'installed', lambda _id: True)
    monkeypatch.setattr(catalog, 'directory', lambda _id: model_dir)
    monkeypatch.setattr(runner, 'LOGS', tmp_path / 'logs')
    monkeypatch.setattr(runner, 'POOL', runner.WorkerPool())
    monkeypatch.setattr(locks, 'SETTINGS', tmp_path / 'settings')
    monkeypatch.setattr(stable, 'VOICES', tmp_path / 'voices')
    with tool.create_runtime(tmp_path / 'jobs') as runtime:
        actor = runtime.authenticate(runtime.create_client('Whisper ZML test', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        try:
            yield runtime, actor, session, str(audio)
        finally:
            runner.release()
            runtime.close_session(actor, session)


def run(transcription, operation, parameters):
    runtime, actor, session, audio = transcription
    job = runtime.submit(actor, session, operation, {'audio': audio, 'device': 'cpu', **parameters})
    return runtime.wait(actor, job['jobId'], timeout=45)


def test_default_zml_dictation_respects_timestamp_flag(transcription):
    job = run(transcription, 'transcribe', {'timestamps': False})
    assert job['state'] == 'Completed', job.get('error')
    output = job['outputs']
    assert output['text'] == 'Bonjour.'
    assert output['segments'] == []
    assert output['runtime'] == 'zml'
    assert output['language'] == 'fr'
    assert output['placement'] == {'backend': 'cpu', 'pjrt': 'cpu', 'device': 'cpu:0', 'shards': 1}
    assert json.loads(Path(output['file']).read_text('utf-8'))['text'] == output['text']
    assert not list(Path(job['workspace']).glob('whisper-zml-*'))


def test_stable_voice_uses_zml_for_the_missing_transcript(transcription):
    job = run(transcription, 'create_stable_voice', {'name': 'Test', 'transcription_runtime': 'zml'})
    assert job['state'] == 'Completed', job.get('error')
    assert job['outputs']['voice']['reference_text'] == 'Bonjour.'


def test_capture_uses_the_words_of_the_generated_take(transcription, monkeypatch):
    runtime, actor, session, audio = transcription
    monkeypatch.setattr(tool.voice_delivery, 'payload_for', lambda *args, **kwargs: ({'language': 'French'}, ''))
    monkeypatch.setattr(runner, 'speak', lambda *args, **kwargs: {'file': audio, 'durationSeconds': 5})
    job = runtime.submit(actor, session, 'capture_voice_take',
                         {'device': 'cpu', 'transcribe': True, 'transcription_runtime': 'zml'})
    job = runtime.wait(actor, job['jobId'], timeout=45)
    assert job['state'] == 'Completed', job.get('error')
    assert job['outputs']['transcript'] == 'Bonjour.'
    assert Path(job['outputs']['file']).is_file()


def test_explicit_zml_without_config_fails(transcription, monkeypatch):
    monkeypatch.delenv('CYTOOLS_WHISPER_ZML_CONFIG')
    assert runner.whisper_runtime() == 'torch'
    job = run(transcription, 'transcribe', {'runtime': 'zml'})
    assert job['state'] == 'Failed'
    assert job['error']['code'] == 'MissingDependency'


def test_cancellation_stops_the_launcher(transcription, monkeypatch, tmp_path):
    marker = tmp_path / 'launcher.pid'
    monkeypatch.setenv('PERSONARP_TEST_LAUNCHER_PID', str(marker))
    runtime, actor, session, audio = transcription
    job = runtime.submit(actor, session, 'transcribe', {'audio': audio, 'device': 'cpu'})
    limit = time.monotonic() + 30
    while not (marker.is_file() and marker.stat().st_size) and time.monotonic() < limit:
        time.sleep(0.05)
    assert marker.is_file() and marker.stat().st_size, runtime.get_job(actor, job['jobId'])
    runtime.cancel(actor, job['jobId'])
    assert runtime.wait(actor, job['jobId'], timeout=25)['state'] == 'Cancelled'
    assert not psutil.pid_exists(int(marker.read_text('ascii')))
