"""Real acceptance of translation in context: the same ambiguous line, with and without it.

Nothing touches your library: the Valdrenn example is imported into a temporary one, where a
short scene is played by hand so that its earlier lines speak of the mountain.

The line, « Le col est fermé depuis trois jours », is ambiguous out of context: a « col » is a
mountain pass, a collar or a neck. It is translated four ways by each model:

  A. the text alone;
  B. the text with the character (her world, how she speaks, where she stands);
  C. only that line of the scene, the lines before it given as context;
  D. the text with a note for the translator.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_translation_context.py [model ...]
Writes data/reports/translation-context.json. About a minute of GPU.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from personarp import library, sessions                                  # noqa: E402
from personarp.paths import DATA                                          # noqa: E402
from personarp.schemas import FORMAT_PERSONA, normalize_persona, normalize_world  # noqa: E402
from personarp.voice import stable                                        # noqa: E402

LINE = '[ton: bas] Le col est fermé depuis trois jours. [pause: 400ms] Personne ne monte plus.'
SCENE = [('user', "On part vers Hautroc demain ? Il faudra passer la montagne avant l'hiver."),
         ('assistant', "Si la neige nous laisse monter. Là-haut, le vent ne pardonne rien."),
         ('user', "Et le passage vers l'est, entre les deux sommets ?"),
         ('assistant', LINE)]
NOTE = "On est au pied d'une montagne enneigée ; « le col » est le passage entre deux sommets."


def run(runtime, actor, session, parameters):
    job = runtime.submit(actor, session, 'translate', parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=900)
    if finished['state'] != 'Completed':
        raise SystemExit('translate failed: %s' % json.dumps(finished.get('error'),
                                                             ensure_ascii=False))
    return finished['outputs']


def verdict(text):
    lowered = text.casefold()
    return {'pass': 'pass' in lowered, 'marksKept': '[ton: bas]' in text
            and '[pause: 400ms]' in text}


def main():
    wanted = sys.argv[1:] or ['', 'qwen3-8b']
    base = Path(tempfile.mkdtemp(prefix='personarp-context-'))
    library.personas = library.Collection(base / 'personas', normalize_persona, FORMAT_PERSONA,
                                          'persona')
    library.worlds = library.Collection(base / 'worlds', normalize_world,
                                        'cytools-personarp-world', 'world')
    library.VOICES = stable.VOICES = base / 'voices'
    sessions.SESSIONS = base / 'sessions'

    from tool import create_runtime
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'line': LINE, 'runs': []}
    with create_runtime(base / 'jobs') as runtime:
        actor = runtime.authenticate(
            runtime.create_client('context', ['filesystemExternal'])['token'])
        session_id = runtime.create_session(actor, temporary=True)['sessionId']
        listed = {item['id']: item for item in runtime.wait(actor, runtime.submit(
            actor, session_id, 'list_examples', {})['jobId'], timeout=60)['outputs']['examples']}
        runtime.wait(actor, runtime.submit(actor, session_id, 'import_personas', {
            'file': listed['01-valdrenn']['file']})['jobId'], timeout=120)
        maelis = next(entry['id'] for entry in library.personas.list() if 'maelis' in entry['id'])
        scene = sessions.create(maelis, 'Vers Hautroc')
        for role, text in SCENE:
            sessions.append_turn(scene, role, text)
        sessions.save(scene)

        cases = [('A. text alone', {'text': LINE, 'source_language': 'French'}),
                 ('B. with the character', {'text': LINE, 'persona_id': maelis}),
                 ('C. in its scene', {'persona_id': maelis, 'session_id': scene['id'],
                                      'turns': [3], 'save': False}),
                 ('D. with a note', {'text': LINE, 'context': NOTE,
                                     'source_language': 'French'})]
        for model in wanted:
            for label, parameters in cases:
                started = time.monotonic()
                outputs = run(runtime, actor, session_id, {
                    **parameters, 'target_language': 'English', 'llm_model': model,
                    'keep_loaded': True})
                text = outputs['text'] or outputs['translations'][0]['text']
                entry = {'case': label, 'model': outputs['model'], 'text': text,
                         'seconds': round(time.monotonic() - started, 1), **verdict(text)}
                report['runs'].append(entry)
                print('%-24s %-12s %-5s %s' % (label, outputs['model'],
                                               'PASS' if entry['pass'] else '-', text), flush=True)
            runtime.wait(actor, runtime.submit(actor, session_id, 'unload_model', {})['jobId'],
                         timeout=120)
    target = DATA / 'reports' / 'translation-context.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Report:', target)


if __name__ == '__main__':
    main()
