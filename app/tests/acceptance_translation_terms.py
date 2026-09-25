"""Real acceptance of the lexicon: the terms of a world read the same in every translation.

Nothing touches your library: the Valdrenn example is imported into a temporary one, and a
scene rich in its terms (Roi-Cendre, Éclat, la Brisure, les Maisons des Marches, Corvanne,
Sylvaines) is translated into English in two separate requests, as two working sessions
would. Then the Roi-Cendre is renamed by hand and a line translated again.

Checked: the terms are rendered once and recorded in the world; both requests use the same
renderings; a rendering set by hand replaces the model's in the next translation; the
delivery marks stay; « nommer », an ordinary verb here, is not held to the glossary.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_translation_terms.py [llm-model]
Writes data/reports/translation-terms.json. About a minute of GPU.
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

SCENE = [
    ('user', 'Parle-moi du Roi-Cendre.'),
    ('assistant', 'Le Roi-Cendre cherche les trois Éclats depuis la Brisure.'),
    ('user', 'Et les Maisons des Marches, elles font quoi ?'),
    ('assistant', 'Les Maisons des Marches se disputent Corvanne pendant que le Roi-Cendre '
                  'avance.'),
    ('user', 'Qui garde les Éclats, alors ?'),
    ('assistant', "Un Éclat dort chez les Sylvaines. [pause: 400ms] Il faut nommer les morts "
                  "avant que le Roi-Cendre ne les lève."),
]


def call(runtime, actor, session, operation, parameters):
    job = runtime.submit(actor, session, operation, parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=900)
    if finished['state'] != 'Completed':
        raise SystemExit('%s failed: %s' % (operation, json.dumps(finished.get('error'),
                                                                  ensure_ascii=False)))
    return finished['outputs']


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else ''
    base = Path(tempfile.mkdtemp(prefix='personarp-terms-'))
    library.personas = library.Collection(base / 'personas', normalize_persona, FORMAT_PERSONA,
                                          'persona')
    library.worlds = library.Collection(base / 'worlds', normalize_world,
                                        'cytools-personarp-world', 'world')
    library.VOICES = stable.VOICES = base / 'voices'
    sessions.SESSIONS = base / 'sessions'

    from tool import create_runtime
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'runs': [], 'failures': []}
    with create_runtime(base / 'jobs') as runtime:
        actor = runtime.authenticate(runtime.create_client('terms', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        examples = {item['id']: item for item in call(runtime, actor, session, 'list_examples',
                                                      {})['examples']}
        call(runtime, actor, session, 'import_personas',
             {'file': examples['01-valdrenn']['file']})
        maelis = next(entry for entry in library.personas.list() if 'maelis' in entry['id'])
        world_id = maelis['world_id']
        scene = sessions.create(maelis['id'], 'Les Éclats')
        for role, text in SCENE:
            sessions.append_turn(scene, role, text)
        sessions.save(scene)

        common = {'persona_id': maelis['id'], 'session_id': scene['id'],
                  'target_language': 'English', 'llm_model': model, 'keep_loaded': True}
        for label, turns in (('first request', [0, 1, 2, 3]), ('second request', [4, 5])):
            started = time.monotonic()
            outputs = call(runtime, actor, session, 'translate', {**common, 'turns': turns})
            entry = {'request': label, 'model': outputs['model'],
                     'seconds': round(time.monotonic() - started, 1),
                     'termsLearned': outputs['termsLearned'], 'terms': outputs['terms'],
                     'termsRetried': outputs['termsRetried'], 'termsMissed': outputs['termsMissed'],
                     'lines': [{'turn': item['turn'], 'original': item['original'],
                                'text': item['text'], 'termsMissed': item['termsMissed']}
                               for item in outputs['translations']]}
            report['runs'].append(entry)
            print('== %s (%s, %.0f s): learned %s, retried %d, missed %d'
                  % (label, outputs['model'], entry['seconds'], outputs['termsLearned'],
                     outputs['termsRetried'], outputs['termsMissed']))
            for line in entry['lines']:
                print('  %d. %s' % (line['turn'], line['text']))
                if line['termsMissed']:
                    print('     not kept:', line['termsMissed'])

        lexicon = call(runtime, actor, session, 'translation_terms',
                       {'world_id': world_id, 'language': 'English'})['terms']
        report['lexicon'] = {item['term']: item['text'] for item in lexicon if item['text']}
        print('== lexicon of the world:', json.dumps(report['lexicon'], ensure_ascii=False))

        # A rendering must be a name: a definition repeated consistently is still wrong.
        for term, rendering in report['lexicon'].items():
            if len(rendering.split()) > 6 or any(mark in rendering for mark in '.;:!?'):
                report['failures'].append('%s rendered as a description: %r' % (term, rendering))
        for run in report['runs']:
            if run['termsMissed']:
                report['failures'].append('%s: %d term(s) not kept'
                                          % (run['request'], run['termsMissed']))
        first, second = report['runs']
        for term in set(first['terms']) & set(second['terms']):
            if first['terms'][term] != second['terms'][term]:
                report['failures'].append('%s rendered two ways' % term)
        for term, rendering in {**first['terms'], **second['terms']}.items():
            if report['lexicon'].get(term) != rendering:
                report['failures'].append('%s used %r but the world records %r'
                                          % (term, rendering, report['lexicon'].get(term)))

        call(runtime, actor, session, 'set_term_translations', {
            'world_id': world_id, 'language': 'English',
            'terms': [{'term': 'Roi-Cendre', 'text': 'the Cinder King'}]})
        outputs = call(runtime, actor, session, 'translate',
                       {**common, 'turns': [5], 'overwrite': True})
        redone = outputs['translations'][0]['text']
        report['byHand'] = {'rendering': 'the Cinder King', 'text': redone,
                            'termsMissed': outputs['translations'][0]['termsMissed']}
        print('== after renaming by hand: %s' % redone)
        if 'cinder king' not in redone.casefold():
            report['failures'].append('the rendering set by hand was not used')
        if '[pause: 400ms]' not in redone:
            report['failures'].append('a delivery mark was lost')
    report['passed'] = not report['failures']
    target = DATA / 'reports' / 'translation-terms.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('failures:', report['failures'] or 'none')
    print('Report:', target)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
