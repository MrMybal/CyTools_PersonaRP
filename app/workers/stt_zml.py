"""Call the locally configured ZML Whisper launcher from the voice engine."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from workers._protocol import WorkerError


CONFIG_ENV = 'CYTOOLS_WHISPER_ZML_CONFIG'
PLATFORMS = {'cpu': 'cpu', 'cuda': 'iree_cuda'}


def _launcher():
    filename = os.environ.get(CONFIG_ENV)
    if not filename:
        raise WorkerError('MissingDependency', f'Set {CONFIG_ENV} to a Whisper ZML configuration file', recoverable=True)
    config = Path(filename)
    try:
        if not config.is_absolute():
            raise ValueError('The configuration path must be absolute')
        launcher = Path(json.loads(config.read_text('utf-8-sig'))['launcher'])
        if not launcher.is_absolute() or not launcher.is_file():
            raise ValueError(f'The launcher must be an existing absolute path: {launcher}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise WorkerError('MissingDependency', f'Invalid {CONFIG_ENV}: {exc}', recoverable=True) from exc
    return config, launcher


def transcribe(request, source, reporter):
    import soundfile as sf

    config, launcher = _launcher()
    device = request.get('device', 'cuda')
    if device not in PLATFORMS:
        raise WorkerError('InvalidParameters', 'Whisper ZML accepts CPU or CUDA')
    try:
        duration = sf.info(source).duration
    except sf.LibsndfileError as exc:
        raise WorkerError('InvalidInput', 'This file could not be read as audio. Supply a WAV or FLAC.') from exc
    if duration < 0.2:
        raise WorkerError('InvalidInput', 'The recording is too short to transcribe.')

    reporter.progress(35, step='Transcribing', message='Whisper ZML, %.1f s' % duration)
    with TemporaryDirectory(prefix='whisper-zml-', dir=request['workspace']) as folder:
        cmd = [sys.executable, '-B', launcher, '--runtime-config', config, '--audio', source,
               '--model', request['model_dir'], '--language', request.get('language') or 'auto',
               '--backend', device, '--workspace', folder, '--max-new-tokens', '256']
        env = dict(os.environ, TEMP=folder, TMP=folder, TMPDIR=folder, PYTHONIOENCODING='utf-8')
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', env=env,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    diagnostics = result.stderr.strip()[-8000:]
    if diagnostics:
        reporter.log(diagnostics, level='Warning' if result.returncode else 'Info')
    if result.returncode:
        raise WorkerError('InferenceFailed', f'Whisper ZML exited with status {result.returncode}',
                          {'device': device, 'diagnostics': diagnostics}, recoverable=True)
    try:
        report = json.loads(result.stdout)
        placement = report['placement']
        if (placement['backend'], placement['pjrt'], placement['shards']) != (device, PLATFORMS[device], 1):
            raise ValueError('Unexpected ZML platform or shard count')
        if device == 'cpu' and placement['device'] != 'cpu:0':
            raise ValueError(f'Unexpected ZML CPU device {placement["device"]}')
        if report['complete'] is not True:
            raise ValueError('Whisper ZML reached its per-window token limit')
        return {'text': report['text'], 'segments': report['segments'] if request.get('timestamps', True) else [],
                'durationSeconds': report['duration'], 'language': report['language'],
                'runtime': 'zml', 'placement': placement}
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkerError('InferenceFailed', f'Invalid Whisper ZML result: {exc}', recoverable=True) from exc
