"""Real speech acceptance: weights are loaded and WAV files are produced.

Runs the whole voice path through the Runtime, exactly as the window and MCP do:
capture a take from a written voice description, transcribe it, register it as a stable
voice, then speak a new line cloned from it and check the two recordings really exist.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_voice.py
Writes data/reports/voice-acceptance.json and the WAV files it produced.
"""
import json
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from personarp.paths import DATA                                    # noqa: E402
from personarp.voice import stable                                  # noqa: E402
from tool import create_runtime                                     # noqa: E402

DESCRIPTION = ('Voix feminine, fin de vingtaine, grave et posee, legerement voilee. '
               'Debit lent, articulation nette, chaleur contenue.')
LINE = ('[ton: bas et curieux] Vous cherchez un livre qui n existe pas encore ? '
        '[pause: 500ms] Mmh. [emotion: malice] Alors il faudra l ecrire.')


def run(runtime, actor, session, operation, parameters, timeout=1800):
    job = runtime.submit(actor, session, operation, parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=timeout)
    if finished['state'] != 'Completed':
        raise SystemExit('%s failed: %s' % (operation, json.dumps(finished.get('error'))))
    return finished['outputs']


def main():
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'steps': []}
    with create_runtime(DATA / 'jobs') as runtime:
        client = runtime.create_client('acceptance-voice', ['network', 'filesystemExternal'])
        actor = runtime.authenticate(client['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']

        models = run(runtime, actor, session, 'list_voice_models', {'verify': False}, 300)
        engine = models['engine']
        report['engine'] = {'installed': engine.get('installed'),
                            'report': engine.get('report')}
        report['models'] = [{'id': m['id'], 'installed': m['installed'],
                             'sizeBytes': m['sizeBytes'], 'verification': m['verification']}
                            for m in models['models']]
        if not engine.get('installed'):
            raise SystemExit('The voice engine is not installed; run app/setup_engine.py voice.')

        personas = run(runtime, actor, session, 'list_personas', {})['personas']
        if not personas:
            raise SystemExit('No character in the library to test with.')
        persona_id = personas[0]['id']

        started = time.monotonic()
        take = run(runtime, actor, session, 'capture_voice_take',
                   {'persona_id': persona_id, 'description': DESCRIPTION,
                    'model': '1.7B-VoiceDesign', 'language': 'French', 'device': 'cuda',
                    'seed': 42, 'transcribe': True})
        report['steps'].append({
            'step': 'capture_voice_take (designed from a written description)',
            'seconds': round(time.monotonic() - started, 1),
            'durationSeconds': take['durationSeconds'], 'inRange': take['inRange'],
            'mode': take['mode'], 'model': take['model'],
            'transcript': take['transcript'], 'file': take['file']})

        started = time.monotonic()
        voice = run(runtime, actor, session, 'create_stable_voice',
                    {'name': 'Acceptance voice', 'audio': take['file'],
                     'transcript': take['transcript'], 'persona_id': persona_id,
                     'attach': False, 'source': 'designed'})
        report['steps'].append({
            'step': 'create_stable_voice',
            'seconds': round(time.monotonic() - started, 1),
            'id': voice['id'], 'locked': voice['voice']['locked'],
            'referenceSeconds': voice['voice']['reference_seconds'],
            'model': voice['voice']['model'], 'warning': voice['warning']})

        started = time.monotonic()
        spoken = run(runtime, actor, session, 'speak',
                     {'text': LINE, 'persona_id': persona_id, 'voice_id': voice['id'],
                      'device': 'cuda'})
        report['steps'].append({
            'step': 'speak (cloned from the stable voice)',
            'seconds': round(time.monotonic() - started, 1),
            'durationSeconds': spoken['durationSeconds'], 'mode': spoken['mode'],
            'model': spoken['model'], 'sampleRate': spoken['sampleRate'],
            'passages': len([s for s in spoken['segments'] if 'text' in s]),
            'pauses': len([s for s in spoken['segments'] if 'pauseSeconds' in s]),
            'note': spoken.get('note', ''), 'file': spoken['file']})

        check = run(runtime, actor, session, 'verify_voice', {'voice_id': voice['id']})
        report['steps'].append({'step': 'verify_voice', 'ok': check['ok'],
                                'reason': check['reason']})
        run(runtime, actor, session, 'release_voice', {})

    # The proof is the audio: copy both recordings next to the report and measure them.
    audio = DATA / 'reports' / 'audio'
    audio.mkdir(parents=True, exist_ok=True)
    import shutil
    import soundfile
    produced = []
    for label, path in (('acceptance-reference.wav', report['steps'][0]['file']),
                        ('acceptance-cloned-line.wav', report['steps'][2]['file'])):
        target = audio / label
        shutil.copyfile(path, target)
        info = soundfile.info(str(target))
        produced.append({'file': str(target), 'seconds': round(info.frames / info.samplerate, 2),
                         'sampleRate': info.samplerate, 'channels': info.channels,
                         'subtype': info.subtype})
    report['produced'] = produced
    if any(item['seconds'] < 1.0 for item in produced):
        raise SystemExit('A produced recording is suspiciously short.')

    output = DATA / 'reports' / 'voice-acceptance.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for step in report['steps']:
        print('%-52s %s' % (step['step'], json.dumps(
            {k: v for k, v in step.items() if k not in ('step', 'file', 'transcript')},
            ensure_ascii=False)))
    for item in produced:
        print('produced %.2f s  %d Hz  %s' % (item['seconds'], item['sampleRate'], item['file']))
    print('report:', output)


if __name__ == '__main__':
    main()
