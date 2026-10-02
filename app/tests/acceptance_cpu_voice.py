"""Speech and transcription on the processor, through the Tool's own operations.

One short French line with the smallest speech model (0.6B CustomVoice, preset speaker), then
Whisper on the same take, both with device='cpu', so a machine without an NVIDIA card is known
to work. The workers are limited to a few threads so the machine stays usable while it runs.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_cpu_voice.py [threads]
Writes data/reports/cpu-voice-acceptance.json.
"""
import json
import os
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

THREADS = sys.argv[1] if len(sys.argv) > 1 else '6'
for variable in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[variable] = THREADS               # inherited by the workers the Tool starts

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

import numpy as np                                                          # noqa: E402
import soundfile as sf                                                      # noqa: E402

import tool                                                                 # noqa: E402

LINE = 'Bonjour. Je parle ce soir sans carte graphique, seulement avec le processeur.'


def words(text):
    text = unicodedata.normalize('NFKD', text.lower())
    return [w for w in ''.join(c if c.isalnum() else ' ' for c in text
                               if not unicodedata.combining(c)).split() if len(w) > 2]


def main():
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'threads': int(THREADS), 'line': LINE}
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        actor = runtime.authenticate(runtime.create_client('CPU', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']

        def run(operation, parameters, timeout=1800):
            began = time.time()
            job = runtime.submit(actor, session, operation, parameters)
            done = runtime.wait(actor, job['jobId'], timeout=timeout)
            return done, round(time.time() - began, 1)

        spoken, seconds = run('speak', {'text': LINE, 'device': 'cpu', 'model': '0.6B-CustomVoice',
                                        'voice': {'language': 'French', 'speaker': 'Ryan'}})
        report['speak'] = {'state': spoken['state'], 'seconds': seconds,
                           'error': spoken.get('error')}
        if spoken['state'] == 'Completed':
            outputs = spoken['outputs']
            audio, rate = sf.read(outputs['file'])
            report['speak'].update(durationSeconds=round(len(audio) / rate, 2),
                                   rms=round(float(np.sqrt(np.mean(np.square(audio)))), 4),
                                   model=outputs.get('model'), mode=outputs.get('mode'),
                                   precision=outputs.get('precision'),
                                   realTimeFactor=round(seconds / max(0.1, len(audio) / rate), 1))
            heard, seconds = run('transcribe', {'audio': outputs['file'], 'device': 'cpu',
                                                'language': 'fr', 'timestamps': False})
            report['transcribe'] = {'state': heard['state'], 'seconds': seconds,
                                    'error': heard.get('error')}
            if heard['state'] == 'Completed':
                text = heard['outputs']['text']
                said, expected = set(words(text)), set(words(LINE))
                report['transcribe'].update(text=text,
                                            wordsFound=round(len(said & expected) / len(expected), 2))
        run('release_voice', {})
    ok = report['speak']['state'] == 'Completed' and report['speak'].get('rms', 0) > 0.01 \
        and report.get('transcribe', {}).get('wordsFound', 0) >= 0.7
    report['ok'] = ok
    output = ROOT / 'data/reports/cpu-voice-acceptance.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
