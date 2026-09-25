"""Create or repair the private voice engine declared in app/engines.json.

    python app/setup_engine.py voice [--cpu-only] [--status] [--status-all]

The environment is created at its final path (runtime/engines/voice) with the base
interpreter of the private runtime; a venv is never moved afterwards, because its scripts
hold absolute paths. PyTorch is installed first from the wheel index declared for the
engine and pinned by a constraints file, so a later dependency cannot silently replace the
CUDA build with a CPU wheel. The last step imports every declared module inside the new
environment: nothing is recorded as installed before that check passes.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
SPEC = json.loads((APP / 'engines.json').read_text('utf-8-sig'))


def log(message):
    print('[setup_engine] ' + message, flush=True)


def base_interpreter():
    # A venv shim cannot reliably create another venv: use the real interpreter.
    return getattr(sys, '_base_executable', None) or sys.executable


def engine_root(name):
    return ROOT / SPEC['engines'][name]['directory']


def engine_python(name):
    root = engine_root(name)
    return root / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def run(command, **kwargs):
    log(' '.join(str(part) for part in command))
    subprocess.run([str(part) for part in command], check=True, **kwargs)


def pip(python, *args, env=None):
    run([python, '-m', 'pip', *args], env=env)


def install_environment(name, cpu_only=False):
    spec = SPEC['engines'][name]
    root = engine_root(name)
    python = engine_python(name)
    if not python.exists():
        root.parent.mkdir(parents=True, exist_ok=True)
        run([base_interpreter(), '-m', 'venv', str(root)])
    pip(python, 'install', '--upgrade', 'pip', 'wheel')
    env = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_KEYRING_PROVIDER='disabled')
    torch_spec = spec.get('torch')
    constraints = []
    if torch_spec:
        block = torch_spec['cpu'] if cpu_only else torch_spec
        pip(python, 'install', '--index-url', block['index'], *block['packages'], env=env)
        constraints = [package.split('+')[0] for package in block['packages']]
        (root / 'cytools-constraints.txt').write_text('\n'.join(constraints) + '\n', 'utf-8')
    arguments = ['install', '-r', str(APP / spec['requirements'])]
    if constraints:
        arguments += ['-c', str(root / 'cytools-constraints.txt')]
    pip(python, *arguments, env=env)
    return python


def verify(name, cpu_only=False):
    spec = SPEC['engines'][name]
    python = engine_python(name)
    modules = spec.get('verify', [])
    script = (
        'import importlib, json, sys\n'
        'report = {"python": sys.version.split()[0], "modules": {}}\n'
        f'for name in {modules!r}:\n'
        '    try:\n'
        '        module = importlib.import_module(name)\n'
        '        report["modules"][name] = getattr(module, "__version__", "ok")\n'
        '    except Exception as exc:\n'
        '        report["modules"][name] = "ERROR: " + str(exc)\n'
        'try:\n'
        '    import torch\n'
        '    report["torch"] = torch.__version__\n'
        '    report["cuda"] = torch.cuda.is_available()\n'
        '    report["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"\n'
        'except Exception:\n'
        '    pass\n'
        'print(json.dumps(report))\n'
    )
    output = subprocess.run([str(python), '-c', script], capture_output=True, text=True, cwd=str(ROOT))
    if output.returncode != 0:
        raise SystemExit('Verification process failed:\n' + output.stderr[-4000:])
    report = json.loads(output.stdout.strip().splitlines()[-1])
    failed = {k: v for k, v in report['modules'].items() if str(v).startswith('ERROR')}
    if failed:
        raise SystemExit('Missing modules in ' + name + ': ' + json.dumps(failed, indent=2))
    if spec.get('torch') and not cpu_only and not report.get('cuda'):
        raise SystemExit('CUDA is not available in the new environment (torch %s). '
                         'Re-run with --cpu-only to accept a CPU engine.' % report.get('torch'))
    return report


def status(name):
    spec = SPEC['engines'][name]
    python = engine_python(name)
    receipt = engine_root(name) / 'cytools-engine.json'
    info = {'engine': name, 'label': spec['label'], 'python': str(python),
            'directory': str(engine_root(name)), 'installed': False, 'report': None,
            'estimatedBytes': spec.get('estimatedBytes', 0), 'notes': spec.get('notes', '')}
    if python.exists() and receipt.is_file():
        try:
            info['report'] = json.loads(receipt.read_text('utf-8'))
            info['installed'] = True
        except ValueError:
            info['report'] = None
    return info


def install(name, cpu_only=False):
    install_environment(name, cpu_only=cpu_only)
    report = verify(name, cpu_only=cpu_only)
    report['cpuOnly'] = bool(cpu_only)
    (engine_root(name) / 'cytools-engine.json').write_text(json.dumps(report, indent=2), 'utf-8')
    log('engine ' + name + ' ready: ' + json.dumps(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('engine', nargs='?', choices=list(SPEC['engines']))
    parser.add_argument('--cpu-only', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--status-all', action='store_true')
    arguments = parser.parse_args()
    if arguments.status_all:
        print(json.dumps({name: status(name) for name in SPEC['engines']}, indent=2))
        return 0
    if not arguments.engine:
        parser.error('engine name required')
    if arguments.status:
        print(json.dumps(status(arguments.engine), indent=2))
        return 0
    install(arguments.engine, cpu_only=arguments.cpu_only)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
