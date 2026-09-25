"""Open every tab of the window in turn and prove each one really drew.

This exists because the earlier check looked only for an error log. A syntax error in a
panel makes the import fail before the log is ever created, so the check reported success
for a window that never started. Here a tab passes only when the process exits cleanly and
leaves a screenshot newer than the moment the run began.

Run: runtime/python/Scripts/python.exe app/tests/smoke_ui.py [tab ...]
Writes data/reports/ui-<tab>.png and data/reports/ui-smoke.json.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
REPORTS = ROOT / 'data/reports'
LOG = ROOT / 'data/logs/desktop-error.log'

TABS = ['Scene', 'Characters', 'Worlds', 'Assistant', 'Voice', 'Batches', 'Library', 'Models',
        'Updates', 'Diagnostics']
SHEET_TABS = {'Characters': ['Identity', 'Appearance', 'Relationships', 'Voice', 'Model'],
              'Library': ['Pictures', 'ComfyUI']}
TIMEOUT = 300


def python():
    return ROOT / ('runtime/python/Scripts/python.exe' if sys.platform == 'win32'
                   else 'runtime/python/bin/python')


def run_tab(tab, sheet='', language=''):
    name = tab if not sheet else '%s-%s' % (tab, sheet)
    if language:
        name = language + '-' + name
    picture = REPORTS / ('ui-%s.png' % name.replace(' ', '-').lower())
    started = time.time()
    LOG.unlink(missing_ok=True)
    command = [str(python()), str(APP / 'desktop.py'), '--smoke-tab', tab, '--strict-ui']
    if sheet:
        command += ['--smoke-sheet', sheet]
    if language:
        command += ['--smoke-language', language]
    try:
        finished = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=TIMEOUT)
        code, output = finished.returncode, (finished.stderr or finished.stdout or '')[-1500:]
    except subprocess.TimeoutExpired:
        return {'tab': name, 'ok': False, 'reason': 'timed out after %ds' % TIMEOUT}

    if code != 0:
        return {'tab': name, 'ok': False, 'reason': 'exit code %d' % code,
                'output': output.strip()[-800:]}
    if LOG.is_file():
        return {'tab': name, 'ok': False, 'reason': 'wrote desktop-error.log',
                'output': LOG.read_text('utf-8', errors='replace')[-800:]}
    if not picture.is_file():
        return {'tab': name, 'ok': False, 'reason': 'no screenshot at %s' % picture}
    if picture.stat().st_mtime < started:
        return {'tab': name, 'ok': False,
                'reason': 'screenshot is stale, the window did not redraw it'}
    return {'tab': name, 'ok': True, 'screenshot': str(picture),
            'seconds': round(time.time() - started, 1),
            'bytes': picture.stat().st_size}


def main():
    arguments = sys.argv[1:]
    language = ''
    if '--language' in arguments:
        position = arguments.index('--language')
        language = arguments[position + 1]
        del arguments[position:position + 2]
    wanted = arguments or TABS
    results = []
    for tab in wanted:
        results.append(run_tab(tab, language=language))
        for sheet in SHEET_TABS.get(tab, []):
            results.append(run_tab(tab, sheet, language=language))
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / 'ui-smoke.json').write_text(
        json.dumps({'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'results': results},
                   ensure_ascii=False, indent=2), encoding='utf-8')
    for item in results:
        print('%-4s %-24s %s' % ('OK' if item['ok'] else 'FAIL', item['tab'],
                                 item.get('reason', '%.1fs' % item.get('seconds', 0))))
        if not item['ok'] and item.get('output'):
            print('     ' + item['output'].replace('\n', '\n     ')[:700])
    failed = [item['tab'] for item in results if not item['ok']]
    print('\n%d of %d tabs drew.' % (len(results) - len(failed), len(results)))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
