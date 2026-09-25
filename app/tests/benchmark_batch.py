"""How fast is a batch on this card? The same lines, spoken with several batch sizes.

Nothing touches your library: the Valdrenn example is imported into a temporary one, exported
with its recordings, and every run is a task bringing that bundle. Each run is checked like
the acceptance (every take present under its id, long enough, not silent) and timed; the
first one also pays the model load, so a one-line warm-up comes first.

Run: runtime/python/Scripts/python.exe app/tests/benchmark_batch.py [--sizes 1,4,8,0] [--repeat 1]
  --sizes   batch sizes to compare; 0 is the automatic size (measured on a first batch of 4)
  --repeat  how many times the 16 lines are repeated (2 gives 32 lines)
Writes data/reports/batch-benchmark-<sizes>-x<repeat>.json. On an RTX 3090, about a minute per size for 16 lines.
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'tests'))

from acceptance_batch import LINES, point_library_at, table, takes, run   # noqa: E402
from personarp.paths import DATA                                           # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sizes', default='1,4,8,0')
    parser.add_argument('--repeat', type=int, default=1)
    arguments = parser.parse_args()
    sizes = [int(value) for value in arguments.sizes.split(',') if value.strip()]
    lines = [('%s-%d' % (identifier, turn), who, text, language)
             for turn in range(1, arguments.repeat + 1)
             for identifier, who, text, language in LINES]

    base = Path(tempfile.mkdtemp(prefix='personarp-bench-'))
    point_library_at(base / 'prepare')
    from tool import create_runtime
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'lines': len(lines), 'runs': []}
    with create_runtime(base / 'jobs') as runtime:
        actor = runtime.authenticate(
            runtime.create_client('benchmark-batch', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        listed = {item['id']: item for item in
                  run(runtime, actor, session, 'list_examples', {})['examples']}
        imported = run(runtime, actor, session, 'import_personas',
                       {'file': listed['01-valdrenn']['file']})
        exported = run(runtime, actor, session, 'export_personas', {
            'persona_ids': imported['personas'], 'include_audio': True})
        bundle = base / 'valdrenn.zip'
        shutil.copyfile(exported['file'], bundle)
        point_library_at(base / 'execute')
        common = {'personas': [str(bundle)], 'use_library': False}

        started = time.monotonic()
        run(runtime, actor, session, 'speak_batch_file', {**common, 'text': table(LINES[:1])})
        report['warmUpSeconds'] = round(time.monotonic() - started, 1)
        print('warm-up %.1f s' % report['warmUpSeconds'], flush=True)

        for size in sizes:
            started = time.monotonic()
            outputs = run(runtime, actor, session, 'speak_batch_file', {
                **common, 'text': table(lines), 'batch_size': size,
                'name': 'taille-%s' % (size or 'auto')})
            seconds = time.monotonic() - started
            checked = takes(outputs)
            audio = sum(line.get('seconds', 0) for line in checked)
            group = outputs['groups'][0] if outputs['groups'] else {}
            entry = {'batchSize': size or 'auto', 'seconds': round(seconds, 1),
                     'audioSeconds': round(audio, 1),
                     'realTimeFactor': round(audio / seconds, 2) if seconds else None,
                     'done': outputs['done'], 'bad': [l for l in checked if not l['ok']],
                     'sizes': group.get('batchSizes'), 'retries': group.get('memoryRetries'),
                     'perPassageGB': round((group.get('perPassageBytes') or 0) / 1024 ** 3, 2),
                     'peakGB': round((group.get('vramPeakBytes') or 0) / 1024 ** 3, 1),
                     'limitGB': round((group.get('limitBytes') or 0) / 1024 ** 3, 1)}
            report['runs'].append(entry)
            print('size %-4s %6.1f s  %5.1f s of audio  x%.2f real time  batches=%s  retries=%s  '
                  'per passage %.2f GB  peak %.1f GB / cap %.1f GB  bad=%d' % (
                      entry['batchSize'], entry['seconds'], entry['audioSeconds'],
                      entry['realTimeFactor'] or 0, entry['sizes'], entry['retries'],
                      entry['perPassageGB'], entry['peakGB'], entry['limitGB'],
                      len(entry['bad'])), flush=True)

    one = next((run_['seconds'] for run_ in report['runs'] if run_['batchSize'] == 1), None)
    for entry in report['runs']:
        entry['speedUp'] = round(one / entry['seconds'], 2) if one else None
    target = DATA / 'reports' / ('batch-benchmark-%s-x%d.json' % (
        '-'.join(str(size or 'auto') for size in sizes), arguments.repeat))
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Report:', target)
    return 0 if all(not entry['bad'] and entry['done'] == len(lines)
                    for entry in report['runs']) else 1


if __name__ == '__main__':
    sys.exit(main())
