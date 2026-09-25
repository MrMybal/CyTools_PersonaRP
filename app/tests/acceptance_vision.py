"""Real vision acceptance: a photograph is attached to a sheet and read by a vision model.

Runs through the Runtime, exactly as the window and MCP do: attach, describe under a
decoding grammar, apply to the sheet, then check that the visual tags reach the image
prompt of a scene directive — which is the point of the whole feature.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_vision.py [image]
Writes data/reports/vision-acceptance.json.
"""
import json
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from personarp import models, scene                            # noqa: E402
from personarp.paths import DATA                               # noqa: E402
from personarp.schemas import normalize_persona                # noqa: E402
from tool import create_runtime                                # noqa: E402


def run(runtime, actor, session, operation, parameters, timeout=1800):
    job = runtime.submit(actor, session, operation, parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=timeout)
    if finished['state'] != 'Completed':
        raise SystemExit('%s failed: %s' % (operation, json.dumps(finished.get('error'))))
    return finished['outputs']


def main():
    picture = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / 'inputs' / 'portrait-test.png'
    if not picture.is_file():
        raise SystemExit('Give a photograph: acceptance_vision.py <image>')
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'picture': str(picture), 'steps': []}

    with create_runtime(DATA / 'jobs') as runtime:
        client = runtime.create_client('acceptance-vision', ['network', 'filesystemExternal'])
        actor = runtime.authenticate(client['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']

        available = models.vision_models()
        report['visionModels'] = [{'id': m, 'projector': str(models.projector_path(m) or '')}
                                  for m in available]
        if not available:
            raise SystemExit('No vision model is installed.')

        # A throwaway character: an acceptance run must never rewrite a sheet you wrote.
        persona_id = run(runtime, actor, session, 'create_persona',
                         {'name': 'Acceptance vision',
                          'persona': {'appearance': {'style_reference': 'photographie'}}})['id']
        report['persona'] = persona_id

        started = time.monotonic()
        added = run(runtime, actor, session, 'add_persona_image',
                    {'persona_id': persona_id, 'image': str(picture), 'role': 'portrait',
                     'caption': 'acceptance run'})
        attached = added['references'][-1]
        report['steps'].append({
            'step': 'add_persona_image', 'seconds': round(time.monotonic() - started, 2),
            'file': attached['file'], 'pixels': '%dx%d' % (attached['width'], attached['height']),
            'sha256': attached['sha256'][:16]})

        started = time.monotonic()
        described = run(runtime, actor, session, 'describe_image',
                        {'persona_id': persona_id, 'file': attached['file'],
                         'use_existing': False, 'language': 'Francais', 'device': 'cuda'})
        report['steps'].append({
            'step': 'describe_image', 'seconds': round(time.monotonic() - started, 2),
            'model': described['model'],
            'sent': '%dx%d' % (described['sentWidth'], described['sentHeight']),
            'fields': sorted(described['proposal']),
            'proposal': described['proposal']})

        applied = run(runtime, actor, session, 'apply_proposal',
                      {'persona_id': persona_id, 'target': 'appearance', 'kind': 'persona',
                       'proposal': described['proposal']})
        sheet = normalize_persona(applied['document'])
        tags = sheet['appearance']['visual_tags']
        report['steps'].append({'step': 'apply_proposal', 'revision': applied['revision'],
                                'visualTags': tags})

        checked = run(runtime, actor, session, 'verify_persona_images',
                      {'persona_id': persona_id})
        report['steps'].append({'step': 'verify_persona_images',
                                'allPresent': all(i['ok'] for i in checked['references'])})

        # The tags must reach the prompt a renderer receives; that is why they were extracted.
        prompts = run(runtime, actor, session, 'scene_prompts',
                      {'scene': {'pose': 'de trois quarts', 'setting': {'location': 'Le Pont'}},
                       'persona_id': persona_id})
        report['steps'].append({
            'step': 'scene_prompts', 'image_prompt': prompts['image_prompt'],
            'tagsReachThePrompt': [t for t in tags if t.lower() in prompts['image_prompt'].lower()]})

        run(runtime, actor, session, 'remove_persona_image',
            {'persona_id': persona_id, 'file': attached['file']})
        run(runtime, actor, session, 'remove_persona', {'persona_id': persona_id})
        run(runtime, actor, session, 'unload_model', {})

    reached = report['steps'][-1]['tagsReachThePrompt']
    if not reached:
        raise SystemExit('The extracted tags never reached the image prompt.')
    output = DATA / 'reports' / 'vision-acceptance.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for step in report['steps']:
        print('%-24s %s' % (step['step'], json.dumps(
            {k: v for k, v in step.items() if k not in ('step', 'proposal')},
            ensure_ascii=False)[:190]))
    print('\nappearance read from the photograph:')
    for key, value in report['steps'][1]['proposal'].items():
        print('  %-14s %s' % (key, json.dumps(value, ensure_ascii=False)
                              if isinstance(value, list) else value))
    print('\nreport:', output)


if __name__ == '__main__':
    main()
