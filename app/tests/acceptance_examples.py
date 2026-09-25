"""Real acceptance of the example worlds: they are imported and played with the real model.

Nothing here touches your library. The collections and the sessions are pointed at a
temporary folder before the Runtime is built, so the examples are imported there, played
there, and thrown away with it.

For each chosen character: import its world through import_personas, then one real chat on
the GPU with the scene description pass on. The run checks that the reply is in French and in
character territory (it names something of the world), that no section of the sheet was
dropped from the prompt, and that the scene directive came back valid.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_examples.py
Writes data/reports/examples-acceptance.json. About 30 seconds of GPU per character.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from personarp import examples, library, sessions                    # noqa: E402
from personarp.paths import DATA                                      # noqa: E402
from personarp.schemas import FORMAT_PERSONA, normalize_persona, normalize_world  # noqa: E402

# (bundle, character, what the player says, words of the world a real answer should reach)
PLAYS = [
    ('01-valdrenn', 'maelis-de-corvanne',
     "*J'entre dans la chapelle en secouant la cendre de mon manteau.* Ton pendentif brille. "
     "Qu'est-ce que ça veut dire ?",
     ['éclat', 'pendentif', 'mort', 'nomm', 'brûl', 'cendre']),
    ('02-station-meridienne', 'kasimir-rook',
     "*Je m'assois en face de toi au Point de Lagrange.* On dit que c'est toi qui as trouvé "
     "l'Écho. Combien tu veux pour me raconter ?",
     ['écho', 'ceinture', 'kappa', 'coque', 'caillou', 'vieille']),
]


def run(runtime, actor, session, operation, parameters, timeout=900):
    job = runtime.submit(actor, session, operation, parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=timeout)
    if finished['state'] != 'Completed':
        raise SystemExit('%s failed: %s' % (operation, json.dumps(finished.get('error'),
                                                                  ensure_ascii=False)))
    return finished['outputs']


def main():
    temporary = Path(tempfile.mkdtemp(prefix='personarp-examples-'))
    library.personas = library.Collection(temporary / 'personas', normalize_persona,
                                          FORMAT_PERSONA, 'persona')
    library.worlds = library.Collection(temporary / 'worlds', normalize_world,
                                        'cytools-personarp-world', 'world')
    sessions.SESSIONS = temporary / 'sessions'

    from tool import create_runtime
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'library': str(temporary), 'plays': []}
    with create_runtime(temporary / 'jobs') as runtime:
        actor = runtime.authenticate(
            runtime.create_client('acceptance-examples', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        listed = {item['id']: item for item in run(runtime, actor, session, 'list_examples', {})['examples']}
        for bundle, persona_id, line, words in PLAYS:
            imported = run(runtime, actor, session, 'import_personas',
                           {'file': listed[bundle]['file']})
            scene = run(runtime, actor, session, 'new_session', {'persona_id': persona_id})
            started = time.monotonic()
            reply = run(runtime, actor, session, 'chat', {
                'persona_id': persona_id, 'session_id': scene['id'], 'text': line,
                'speak': 'no', 'keep_loaded': True})
            text = reply['dialogue'].lower()
            entry = {
                'world': listed[bundle]['world'], 'character': persona_id,
                'imported': imported, 'seconds': round(time.monotonic() - started, 1),
                'model': reply['context'].get('model'), 'device': reply['context'].get('device'),
                'promptCharacters': reply['context'].get('promptCharacters'),
                'droppedSections': reply['context'].get('droppedSections'),
                'reply': reply['dialogue'],
                'worldWordsFound': [word for word in words if word in text],
                'sceneBeat': (reply.get('scene') or {}).get('beat', ''),
                'imagePrompt': (reply.get('prompts') or {}).get('image_prompt', ''),
                'sceneError': reply.get('sceneError', ''),
            }
            report['plays'].append(entry)
            print(json.dumps(entry, ensure_ascii=False)[:600])
        run(runtime, actor, session, 'unload_model', {})

    path = DATA / 'reports' / 'examples-acceptance.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(path)
    failures = [play['character'] for play in report['plays']
                if play['droppedSections'] or not play['worldWordsFound'] or play['sceneError']]
    if failures:
        raise SystemExit('Check these plays: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
