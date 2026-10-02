"""The Windows binary release, run the way someone who downloaded it would run it.

The portable zip is extracted into a new folder whose name has a space, far from this
project, and everything below runs from there with a bare environment: PATH reduced to
Windows itself (no Python, no git), no PYTHON* variable, a working directory outside the
package.

- the folder holds what a user expects at the root, and nothing else;
- the private interpreter takes its standard library and every package from the package,
  and the per-user site-packages are off;
- the CLI answers (describe, an operation);
- a real MCP session over stdio lists the tools and runs operations, including importing an
  example world;
- CyTools_PersonaRP.exe, started from another directory, opens the window on two tabs and
  leaves fresh screenshots, with no error log;
- a virtual environment can be created from the private interpreter, as the voice engine
  setup does;
- with --tests, pytest is added to the extracted copy (only) and the whole suite runs there.

No model and no engine is part of the release, so no generation runs here.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_release.py [zip] [--tests] [--keep]
Writes data/reports/release-acceptance.json.
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import psutil

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
NAME = 'CyTools_PersonaRP'
EXPECTED_ROOT = {NAME + '.exe', 'LICENSE', 'LICENCES', 'LISEZ-MOI.md', 'README.md', 'app', 'data',
                 'runtime'}
NOTICES = {'CyToolsCore-MIT.txt', 'SOURCES.txt', 'Python-Runtime-Notices.txt'}
SDK_PROBE = ('import json, importlib.metadata as m\n'
             'found = [d for d in m.distributions()\n'
             '         if (d.metadata["Name"] or "").lower().replace("_", "-") == "cytools-core"]\n'
             'text = (found[0].read_text("licenses/LICENSE") or "") if found else ""\n'
             'print(json.dumps({"copies": len(found),\n'
             '                  "version": found[0].version if found else "",\n'
             '                  "expression": found[0].metadata.get("License-Expression") if found else "",\n'
             '                  "mit": text.startswith("MIT License"), "gpl": "GNU GENERAL" in text}))\n')
PROBE = ('import sys, site, json, importlib\n'
         'names = ["cytools_core", "imgui_bundle", "numpy", "PIL", "soundfile", "sounddevice",\n'
         '         "gguf", "win32api", "mcp", "psutil", "venv", "ensurepip", "ssl", "sqlite3"]\n'
         'files = {n: getattr(importlib.import_module(n), "__file__", "") for n in names}\n'
         'print(json.dumps({"executable": sys.executable, "prefix": sys.prefix, "path": sys.path,\n'
         '                  "userSite": site.ENABLE_USER_SITE, "files": files}))\n')


def bare_environment():
    """What a machine without Python or git would give the program."""
    windows = os.environ.get('SystemRoot', r'C:\Windows')
    keep = ('SystemRoot', 'SystemDrive', 'windir', 'TEMP', 'TMP', 'USERPROFILE', 'APPDATA',
            'LOCALAPPDATA', 'HOMEDRIVE', 'HOMEPATH', 'USERNAME', 'COMPUTERNAME', 'ProgramData',
            'ProgramFiles', 'ProgramFiles(x86)', 'CommonProgramFiles', 'NUMBER_OF_PROCESSORS',
            'PROCESSOR_ARCHITECTURE', 'OS', 'PATHEXT', 'ComSpec')
    environment = {key: os.environ[key] for key in keep if key in os.environ}
    environment['PATH'] = os.pathsep.join([windows + r'\System32', windows,
                                           windows + r'\System32\Wbem'])
    return environment


def run(command, cwd, timeout=600):
    finished = subprocess.run([str(part) for part in command], cwd=str(cwd), capture_output=True,
                              env=bare_environment(), timeout=timeout)
    return (finished.returncode, finished.stdout.decode('utf-8', 'replace'),
            finished.stderr.decode('utf-8', 'replace'))


def inside(path, root):
    return str(Path(path).resolve()).casefold().startswith(str(root.resolve()).casefold())


def check_layout(root):
    present = set(os.listdir(root))
    runtime = set(os.listdir(root / 'runtime'))
    notices = set(os.listdir(root / 'LICENCES')) if (root / 'LICENCES').is_dir() else set()
    core = root / 'LICENCES' / 'CyToolsCore-MIT.txt'
    core_text = core.read_text(encoding='utf-8') if core.is_file() else ''
    scaffold = root / 'app' / 'LICENSE-CyToolsCore.txt'
    ok = present == EXPECTED_ROOT and {'bootstrap.py', 'python', 'build-info.json'} <= runtime \
        and not any((root / 'data').iterdir()) and NOTICES <= notices \
        and core_text.startswith('MIT License') and 'Copyright (c) 2026 Cyberalien' in core_text \
        and scaffold.is_file() and scaffold.read_text(encoding='utf-8') == core_text
    return ok, {'root': sorted(present), 'runtime': sorted(runtime), 'licences': sorted(notices)}


def check_sdk(root, python, elsewhere):
    """The SDK really shipped: one copy, 0.10.1 or later, MIT, no GPL copy left behind."""
    code, out, err = run([python, '-c', SDK_PROBE], elsewhere)
    if code:
        return False, {'error': err[-800:]}
    seen = json.loads(out)
    version = tuple(int(part) for part in seen['version'].split('.')[:3]) if seen['version'] else ()
    ok = seen['copies'] == 1 and version >= (0, 10, 1) and seen['expression'] == 'MIT' \
        and seen['mit'] and not seen['gpl']
    return ok, seen


def shadowed(python, folder):
    """Plant a module in a per-user site-packages and see whether this interpreter imports it."""
    user_base = folder / 'user base'
    packages = user_base / 'Python311' / 'site-packages'
    packages.mkdir(parents=True, exist_ok=True)
    (packages / 'shadow_probe.py').write_text('PLANTED = True\n', encoding='utf-8')
    environment = dict(bare_environment(), PYTHONUSERBASE=str(user_base))
    finished = subprocess.run([str(python), '-c', 'import shadow_probe'], cwd=str(folder),
                              env=environment, capture_output=True, timeout=60)
    return finished.returncode == 0


def check_interpreter(root, python, elsewhere):
    code, out, err = run([python, '-c', PROBE], elsewhere)
    if code:
        return False, {'error': err[-800:]}
    seen = json.loads(out)
    outside = [entry for entry in seen['path'] + list(seen['files'].values())
               if entry and not inside(entry, root)]
    # The control: an ordinary CPython 3.11 of this machine, if there is one, does import it.
    control = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Python/Python311/python.exe'
    reached = shadowed(python, elsewhere)
    control_reached = shadowed(control, elsewhere) if control.is_file() else None
    return (seen['userSite'] is False and inside(seen['prefix'], root) and not outside
            and not reached and control_reached is not False,
            {'prefix': seen['prefix'], 'userSite': seen['userSite'], 'outside': outside,
             'modules': len(seen['files']), 'plantedUserPackageImported': reached,
             'controlInterpreterImportsIt': control_reached})


def check_cli(root, python, elsewhere):
    code, out, err = run([python, root / 'app/tool.py', 'describe'], elsewhere)
    described = json.loads(out) if code == 0 else {}
    manifest = described.get('manifest', described)
    code2, out2, err2 = run([python, root / 'app/tool.py', 'invoke', 'list_examples'], elsewhere)
    job = json.loads(out2) if code2 == 0 else {}
    examples = (job.get('outputs') or {}).get('examples', [])
    ok = code == 0 and manifest.get('id') == 'cy.tool.personarp' and job.get('state') == 'Completed' \
        and len(examples) == 6
    return ok, {'id': manifest.get('id'), 'version': manifest.get('version'),
                'examples': [example.get('world') for example in examples],
                'errors': [text[-400:] for text in (err, err2) if text.strip() and not ok]}


async def _mcp(root, python, elsewhere):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def call(session, name, parameters, timeout=120):
        arguments = parameters if name.startswith('cy_') else {'parameters': parameters}
        result = await session.call_tool(name, arguments)
        if result.isError:
            raise RuntimeError('%s: %s' % (name, result.content[0].text))
        job = json.loads(result.content[0].text)
        deadline = time.monotonic() + timeout
        while 'jobId' in job and job['state'] not in ('Completed', 'Failed', 'Cancelled'):
            if time.monotonic() > deadline:
                raise TimeoutError(name)
            await asyncio.sleep(0.2)
            job = json.loads((await session.call_tool('cy_get_job', {'jobId': job['jobId']}))
                             .content[0].text)
        if job.get('state', 'Completed') != 'Completed':
            raise RuntimeError('%s: %s' % (name, json.dumps(job.get('error'))))
        return job.get('outputs', job)

    # Importing a file is reserved to a client granted filesystemExternal, as a user would
    # create it; the token goes through the environment, never a command line or the report.
    code, out, err = run([python, root / 'app/tool.py', 'create-client', '--name', 'acceptance',
                          '--permission', 'filesystemExternal'], elsewhere)
    if code:
        raise RuntimeError('create-client: ' + err[-400:])
    environment = dict(bare_environment(), CYTOOLS_TOKEN=json.loads(out)['token'])
    server = StdioServerParameters(command=str(python), args=[str(root / 'app/tool.py'), 'mcp'],
                                   cwd=str(elsewhere), env=environment)
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(tool.name for tool in (await session.list_tools()).tools)
            examples = (await call(session, 'op_list_examples', {}))['examples']
            first = examples[0]
            imported = await call(session, 'op_import_personas', {'file': first['file']})
            personas = (await call(session, 'op_list_personas', {}))['personas']
            preview = await call(session, 'op_preview_prompt',
                                 {'persona_id': personas[0]['id'], 'text': 'Bonjour.'})
            # The runtime status (fixed in SDK 0.10), then an AI task of its own: a result
            # written in its workspace, exported, and the task cleaned up afterwards.
            status = json.loads((await session.call_tool('cy_status', {})).content[0].text)
            task = json.loads((await session.call_tool('cy_begin_task', {})).content[0].text)
            task_id = task.get('sessionId') or task.get('result', {}).get('sessionId')
            built = await session.call_tool('op_scene_prompts', {
                'parameters': {'scene': {}, 'persona_id': personas[0]['id']}, 'sessionId': task_id})
            job = json.loads(built.content[0].text)
            while job.get('state') not in ('Completed', 'Failed', 'Cancelled'):
                await asyncio.sleep(0.2)
                job = json.loads((await session.call_tool('cy_get_job', {'jobId': job['jobId']}))
                                 .content[0].text)
            destination = elsewhere / 'exported'
            exported = await session.call_tool('cy_export_job', {'jobId': job['jobId'],
                                                                'destination': str(destination)})
            finished = await session.call_tool('cy_finish_task', {'sessionId': task_id})
            workspace = Path(job.get('workspace', ''))
            deadline = time.monotonic() + 10
            while workspace.exists() and time.monotonic() < deadline:
                await asyncio.sleep(0.2)
    return {'tools': len(tools), 'operations': sum(name.startswith('op_') for name in tools),
            'imported': first['world'], 'importOutputs': sorted(imported),
            'personas': [persona['id'] for persona in personas],
            'promptCharacters': preview['context']['promptCharacters'],
            'runtimeStatus': {key: status.get(key, status.get('result', {}).get(key))
                              for key in ('toolId', 'runningJobs', 'runningWorkers')},
            'taskJob': job.get('state'), 'exportError': exported.isError,
            'exportedFiles': sorted(path.name for path in destination.rglob('*') if path.is_file()),
            'finishError': finished.isError, 'workspaceRemoved': not workspace.exists()}


def _leaves(error):
    if isinstance(error, BaseExceptionGroup):
        return [leaf for inner in error.exceptions for leaf in _leaves(inner)]
    return [error]


def check_mcp(root, python, elsewhere):
    try:
        seen = asyncio.run(_mcp(root, python, elsewhere))
    except Exception as error:                                   # reported, never hidden
        return False, {'error': ['%s: %s' % (type(leaf).__name__, str(leaf)[:600])
                                 for leaf in _leaves(error)]}
    ok = seen['operations'] >= 60 and len(seen['personas']) >= 3 and seen['promptCharacters'] > 0 \
        and seen['runtimeStatus'].get('toolId') == 'cy.tool.personarp' \
        and seen['taskJob'] == 'Completed' and not seen['exportError'] \
        and 'scene.json' in seen['exportedFiles'] and not seen['finishError'] \
        and seen['workspaceRemoved']
    return ok, seen


def check_window(root, elsewhere, tabs=('Scene', 'Models')):
    pythonw = (root / 'runtime/python/Scripts/pythonw.exe').resolve()
    shots, problems = {}, []
    for tab in tabs:
        started = time.time()
        subprocess.run([str(root / (NAME + '.exe')), '--smoke-tab', tab, '--strict-ui'],
                       cwd=str(elsewhere), env=bare_environment(), timeout=30)
        deadline, children = time.time() + 180, []
        while time.time() < deadline:
            children = [process for process in psutil.process_iter(['exe'])
                        if process.info['exe'] and Path(process.info['exe']).resolve() == pythonw]
            if children or time.time() - started > 20:
                break
            time.sleep(0.2)
        codes = []
        for process in children:
            try:
                codes.append(process.wait(max(1, deadline - time.time())))
            except psutil.TimeoutExpired:
                process.kill()
                codes.append('timeout')
        picture = root / 'data/reports' / ('ui-%s.png' % tab.lower())
        fresh = picture.is_file() and picture.stat().st_mtime >= started - 1
        logs = [path.name for path in (root / 'data/logs').glob('*error*.log')] \
            if (root / 'data/logs').is_dir() else []
        shots[tab] = {'process': bool(children), 'exitCodes': codes, 'screenshot': fresh,
                      'bytes': picture.stat().st_size if picture.is_file() else 0}
        if not children or not fresh or logs or any(code not in (0, None) for code in codes):
            problems.append({'tab': tab, 'errorLogs': logs,
                             'log': [(root / 'data/logs' / name).read_text('utf-8', 'replace')[-800:]
                                     for name in logs]})
    folders = sorted(path.name for path in (root / 'data').iterdir() if path.is_dir())
    return not problems, {'tabs': shots, 'problems': problems, 'dataFolders': folders}


def check_venv(root, python, elsewhere):
    probe = root / 'runtime' / 'engines' / 'probe-venv'
    code, _, err = run([python, '-m', 'venv', probe], elsewhere)
    if code:
        return False, {'error': err[-800:]}
    inner = probe / 'Scripts' / 'python.exe'
    code, out, err2 = run([inner, '-c', 'import sys, json; print(json.dumps([sys.prefix, sys.base_prefix]))'],
                          elsewhere)
    code2, pip, _ = run([inner, '-m', 'pip', '--version'], elsewhere)
    prefix, base = json.loads(out) if code == 0 else ('', '')
    shutil.rmtree(probe, ignore_errors=True)
    return (code == 0 and code2 == 0 and inside(base, root) and inside(prefix, probe),
            {'basePrefixInsidePackage': bool(base) and inside(base, root), 'pip': pip.split(' from ')[0]})


def check_tests(root, python):
    code, _, err = run([python, '-m', 'pip', 'install', '--isolated', '-q', '--disable-pip-version-check',
                        'pytest==9.1.1'], root)
    if code:
        # pip needs the network; the bare PATH has no git, which pytest does not need.
        return False, {'error': 'pytest could not be installed: ' + err[-600:]}
    code, out, err = run([python, '-m', 'pytest', 'app/tests', '-q', '-p', 'no:cacheprovider'], root,
                         timeout=1200)
    summary = next((line for line in reversed(out.splitlines()) if re.search(r'\d+ passed', line)), '')
    return code == 0, {'summary': summary.strip('= '), 'tail': out[-1500:] if code else ''}


def main():
    version = json.loads((APP / 'release.json').read_text(encoding='utf-8'))['version']
    default = ROOT / 'runtime/build/release' / version / ('%s-%s-windows-x64.zip' % (NAME, version))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('zip', nargs='?', default=str(default))
    parser.add_argument('--tests', action='store_true', help='also run the test suite in the copy')
    parser.add_argument('--keep', action='store_true', help='keep the extracted copy')
    parser.add_argument('--only', default='', help='comma-separated checks to run, e.g. mcp,cli')
    parser.add_argument('--report', default=str(ROOT / 'data/reports/release-acceptance.json'),
                        help='where the JSON report is written (it may live outside the Tool)')
    options = parser.parse_args()
    only = {name for name in options.only.split(',') if name}
    package = Path(options.zip)
    folder = Path(tempfile.mkdtemp(prefix='PersonaRP release '))
    elsewhere = folder / 'somewhere else'
    elsewhere.mkdir()
    with zipfile.ZipFile(package) as archive:
        archive.extractall(folder)
    root = folder / NAME
    python = root / 'runtime/python/Scripts/python.exe'
    checks = {}
    try:
        for name, check in (('layout', lambda: check_layout(root)),
                            ('interpreter', lambda: check_interpreter(root, python, elsewhere)),
                            ('cli', lambda: check_cli(root, python, elsewhere)),
                            ('mcp', lambda: check_mcp(root, python, elsewhere)),
                            ('window', lambda: check_window(root, elsewhere)),
                            ('venv', lambda: check_venv(root, python, elsewhere)),
                            ('sdk', lambda: check_sdk(root, python, elsewhere))) + \
                (((('tests', lambda: check_tests(root, python)),) if options.tests else ())):
            if only and name not in only:
                continue
            began = time.time()
            ok, detail = check()
            checks[name] = {'ok': ok, 'seconds': round(time.time() - began, 1), **detail}
            print('%-12s %s  %s' % (name, 'OK  ' if ok else 'FAIL', json.dumps(detail, ensure_ascii=False)[:300]),
                  flush=True)
    finally:
        if not options.keep:
            shutil.rmtree(folder, ignore_errors=True)
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'package': package.name,
              'bytes': package.stat().st_size, 'extractedTo': 'a new temporary folder with a space in its name',
              'environment': 'PATH reduced to Windows, no PYTHON* variable, working directory outside the package',
              'checks': checks, 'kept': str(folder) if options.keep else ''}
    output = Path(options.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    failed = [name for name, check in checks.items() if not check['ok']]
    print('report:', output)
    print('FAILED: ' + ', '.join(failed) if failed else 'all checks passed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
