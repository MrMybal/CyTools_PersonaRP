"""Build the Windows binary release: a portable folder that runs without any Python on the
machine, and the application archive the Updates tab expects.

Run: runtime/python/Scripts/python.exe app/build_release.py [--python <CPython 3.11 folder>]
                                                             [--allow-dirty]

Output, in runtime/build/release/<version>/:

    CyTools_PersonaRP-<version>-windows-x64.zip   launcher, app/, runtime/ with a private
                                                   CPython and the application's packages;
                                                   no model, no engine, no user data
    cytools-app.zip                                app/ alone, for the application update stream
    SHA256SUMS.txt

The files come from the commit HEAD (git archive), not from the working folder, so the package
holds exactly what the repository holds; a working folder with uncommitted changes is refused.

The private CPython is a copy of an official CPython 3.11 installation (the one the development
runtime was created from, unless --python names another), without site-packages, caches, Tk,
IDLE or the test suite. Its interpreter lives in runtime/python/Scripts, next to the DLLs it
loads, so every path the Tool already uses (the launcher, the manifest, the ComfyUI nodes, the
voice engine setup) finds it where a virtual environment would have put it; Python finds Lib/
by searching upwards from the executable.

runtime/python/pyvenv.cfg holds only `include-system-site-packages = false`. With no `home`
line, the interpreter still takes this folder as its own installation, but site.py (frozen into
the 3.11 executable, so editing Lib/site.py would change nothing) reads that line and turns the
per-user site-packages off: packages someone installed for their own Python 3.11 can never
shadow the Tool's. Packages are installed at the versions of the development runtime the tests
ran with (constraints taken from its pip freeze), without byte-code, and every path of the build
machine is checked for before anything is archived.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
NAME = 'CyTools_PersonaRP'
BUILD = ROOT / 'runtime' / 'build' / 'release'
# The repository's own files that make no sense in a Windows binary package.
# docs/ holds the screenshots of the GitHub page, not something the application uses.
LEFT_OUT = {'.gitignore', '.gitattributes', NAME + '.sh', 'docs'}
INTERPRETER = ('python.exe', 'pythonw.exe', 'python3.dll', 'python311.dll',
               'vcruntime140.dll', 'vcruntime140_1.dll')
PYTHON_FOLDERS = ('DLLs', 'Lib', 'libs', 'include')
# Tk and IDLE have no use here; the test suite and caches are large and would carry the paths
# of the machine the stdlib was compiled on.
PYTHON_SKIP = {'__pycache__', 'site-packages', 'test', 'idlelib', 'tkinter', 'turtledemo',
               '_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll'}
# Only needed to run the tests; never part of the package.
TEST_ONLY = {'pytest', 'iniconfig', 'pluggy', 'pygments'}
# No "home" line: the interpreter keeps runtime/python as its prefix, and site.py only reads
# this switch. (Python compares keys, so a comment line must not contain an equals sign.)
PYVENV = ('# Private runtime of CyTools_PersonaRP: per-user site-packages never apply.\n'
          'include-system-site-packages = false\n')


def run(command, **options):
    options.setdefault('check', True)
    return subprocess.run([str(part) for part in command], **options)


def git(*arguments):
    return run(['git', '-C', ROOT, *arguments], capture_output=True, text=True).stdout.strip()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def clean_environment():
    """No variable of the build machine may steer the private interpreter or pip."""
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(('PYTHON', 'PIP_', 'VIRTUAL_ENV', 'CONDA'))}
    environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONUTF8='1')
    return environment


def base_python(requested):
    if requested:
        return Path(requested)
    for line in (ROOT / 'runtime/python/pyvenv.cfg').read_text(encoding='utf-8').splitlines():
        key, _, value = line.partition('=')
        if key.strip() == 'home':
            return Path(value.strip())
    raise SystemExit('No --python given and runtime/python/pyvenv.cfg names no base interpreter.')


def export_commit(stage):
    """HEAD as git holds it (line endings of the index, attributes applied)."""
    archive = run(['git', '-C', ROOT, 'archive', '--format=tar', 'HEAD'], capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        members = [member for member in tar.getmembers()
                   if member.name.split('/')[0] not in LEFT_OUT]
        tar.extractall(stage, members=members, filter='data')


def build_launcher(stage):
    run(['cmd', '/c', APP / 'build_launcher.cmd'], cwd=ROOT, capture_output=True)
    built = ROOT / (NAME + '.exe')
    if not built.is_file() or built.stat().st_mtime < time.time() - 120:
        raise SystemExit('The launcher was not rebuilt; run app/build_launcher.cmd and read its output.')
    shutil.copy2(built, stage / built.name)


def copy_python(base, target):
    version = run([base / 'python.exe', '-c', 'import sys; print("%d.%d.%d" % sys.version_info[:3])'],
                  capture_output=True, text=True, env=clean_environment()).stdout.strip()
    if not version.startswith('3.11.'):
        raise SystemExit('The runtime ABI of this Tool is Python 3.11; %s is %s.' % (base, version))
    target.mkdir(parents=True)
    shutil.copy2(base / 'LICENSE.txt', target / 'LICENSE.txt')
    ignore = lambda folder, names: [name for name in names if name in PYTHON_SKIP]
    for name in PYTHON_FOLDERS:
        shutil.copytree(base / name, target / name, ignore=ignore)
    (target / 'Lib' / 'site-packages').mkdir()
    # Only in Scripts: an interpreter at the top would take the parent folder for its prefix
    # once pyvenv.cfg is there (site.py looks for it next to the executable first).
    scripts = target / 'Scripts'
    scripts.mkdir()
    for name in INTERPRETER:
        shutil.copy2(base / name, scripts / name)
    (target / 'pyvenv.cfg').write_text(PYVENV, encoding='utf-8')
    return version


def constraints(folder):
    """The versions the development runtime was tested with."""
    frozen = run([ROOT / 'runtime/python/Scripts/python.exe', '-m', 'pip', 'freeze', '--all'],
                 capture_output=True, text=True, env=clean_environment()).stdout.splitlines()
    kept = [line for line in frozen if '==' in line
            and line.split('==')[0].strip().lower() not in TEST_ONLY | {'cytools-core'}]
    path = folder / 'constraints.txt'
    path.write_text('\n'.join(kept) + '\n', encoding='utf-8')
    return path


def install_packages(python, requirements, pinned):
    environment = clean_environment()
    run([python, '-m', 'ensurepip', '--default-pip'], env=environment, capture_output=True)
    run([python, '-m', 'pip', 'install', '--isolated', '--no-compile', '--no-warn-script-location',
         '--disable-pip-version-check', '--progress-bar', 'off', '-q',
         '-r', requirements, '-c', pinned], env=environment)


def tidy_python(target):
    """Remove what pip leaves that would carry the build machine: console-script wrappers hold
    the absolute path of the interpreter they were made for, byte-code holds source paths."""
    for path in (target / 'Scripts').iterdir():
        if path.name not in INTERPRETER:
            path.unlink()
    for cache in [path for path in target.rglob('__pycache__') if path.is_dir()]:
        shutil.rmtree(cache)
    for path in target.rglob('*.py[co]'):
        path.unlink()


def third_party(python, target, python_version):
    script = ('import importlib.metadata as m, json\n'
              'rows = []\n'
              'for d in m.distributions():\n'
              '    meta = d.metadata\n'
              '    classifiers = [c.split(" :: ")[-1] for c in meta.get_all("Classifier") or []\n'
              '                   if c.startswith("License ::")]\n'
              '    free_text = ((meta.get("License") or "").strip().splitlines() or [""])[0]\n'
              '    licence = meta.get("License-Expression") or "; ".join(classifiers) or free_text\n'
              '    rows.append((meta["Name"], d.version, licence[:120] or "see its dist-info"))\n'
              'print(json.dumps(sorted(rows, key=lambda r: r[0].lower())))\n')
    rows = json.loads(run([python, '-c', script], capture_output=True, text=True,
                          env=clean_environment()).stdout)
    lines = ['# Third-party software in this runtime', '',
             'The private Python of CyTools PersonaRP. Each package keeps its licence text in its',
             '`Lib/site-packages/<name>.dist-info` folder; CPython\'s is `LICENSE.txt` here.', '',
             '| Package | Version | Licence |', '| --- | --- | --- |',
             '| CPython | %s | PSF-2.0 (`LICENSE.txt`) |' % python_version]
    lines += ['| %s | %s | %s |' % tuple(cell.replace('|', '/') for cell in row) for row in rows]
    (target / 'THIRD-PARTY.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    # The same list beside the other notices, where LICENCES/SOURCES.txt says it is.
    notices = ['Python runtime of the CyTools PersonaRP Windows release (runtime/python)', '',
               'Each component keeps its own licence. The full texts are in the release:',
               '  CPython          runtime/python/LICENSE.txt',
               '  each package     runtime/python/Lib/site-packages/<package>.dist-info/',
               'Sources: https://www.python.org/downloads/source/ and '
               'https://pypi.org/project/<package>/',
               '', '%-28s %-14s %s' % ('Component', 'Version', 'Licence'),
               '%-28s %-14s %s' % ('CPython', python_version, 'PSF-2.0')]
    notices += ['%-28s %-14s %s' % tuple(row) for row in rows]
    (target.parent.parent / 'LICENCES' / 'Python-Runtime-Notices.txt').write_text(
        '\n'.join(notices) + '\n', encoding='utf-8')
    return rows


def check_isolation(stage, python):
    """Run the packaged interpreter from elsewhere and see where everything comes from."""
    probe = ('import sys, site, json, importlib\n'
             'names = ["cytools_core", "imgui_bundle", "numpy", "PIL", "soundfile", "sounddevice",\n'
             '         "gguf", "win32api", "mcp", "psutil", "venv", "ensurepip", "ssl", "sqlite3"]\n'
             'files = {n: getattr(importlib.import_module(n), "__file__", "") for n in names}\n'
             'print(json.dumps({"prefix": sys.prefix, "base": sys.base_prefix, "path": sys.path,\n'
             '                  "userSite": site.ENABLE_USER_SITE, "files": files}))\n')
    # As a user's machine would start it: PYTHONNOUSERSITE would hide the very thing checked.
    environment = clean_environment()
    environment.pop('PYTHONNOUSERSITE')
    seen = json.loads(run([python, '-c', probe], capture_output=True, text=True, cwd=BUILD,
                          env=environment).stdout)
    inside = str(stage.resolve()).casefold()
    outside = [entry for entry in seen['path'] + list(seen['files'].values())
               if entry and not str(Path(entry).resolve()).casefold().startswith(inside)]
    if seen['userSite'] is not False or outside:
        raise SystemExit('The packaged interpreter reaches outside the package: %s' % outside)
    return seen


def short_path(path):
    """The 8.3 form Windows hands some programs (C:\\Users\\ABCDEF~1\\...)."""
    import ctypes
    buffer = ctypes.create_unicode_buffer(1024)
    ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, 1024)
    return buffer.value or str(path)


def check_no_build_paths(stage, base):
    """No file of the package may name this machine's folders, account or name."""
    needles = {str(stage), str(ROOT), str(base), str(Path.home()), short_path(Path.home()),
               socket.gethostname()}
    needles = {variant for needle in needles
               for variant in (needle, needle.replace('\\', '/'), needle.replace('\\', '\\\\'))}
    patterns = [needle.casefold().encode('utf-8') for needle in needles if len(needle) > 3]
    patterns += [needle.casefold().encode('utf-16-le') for needle in needles if len(needle) > 3]
    found = []
    for path in stage.rglob('*'):
        if path.is_file():
            data = path.read_bytes().lower()
            if any(pattern in data for pattern in patterns):
                found.append(str(path.relative_to(stage)))
    if found:
        raise SystemExit('Paths of the build machine found in: %s' % found[:20])


def archive(folder, destination, top):
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(folder.rglob('*')):
            name = (top + '/' + path.relative_to(folder).as_posix()) if top else \
                path.relative_to(folder).as_posix()
            if path.is_dir():
                if not any(path.iterdir()):
                    bundle.writestr(name + '/', b'')
            else:
                bundle.write(path, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--python', default='', help='an official CPython 3.11 installation folder')
    parser.add_argument('--allow-dirty', action='store_true',
                        help='build HEAD even though the working folder has uncommitted changes')
    options = parser.parse_args()
    if git('status', '--porcelain') and not options.allow_dirty:
        raise SystemExit('Uncommitted changes: the package is built from HEAD; commit first.')
    release = json.loads((APP / 'release.json').read_text(encoding='utf-8'))
    version, commit = release['version'], git('rev-parse', 'HEAD')
    output = BUILD / version
    if output.exists():
        shutil.rmtree(output)
    stage = output / NAME
    stage.mkdir(parents=True)
    started = time.time()

    print('1/7 files of commit %s' % commit[:12], flush=True)
    export_commit(stage)
    (stage / 'data').mkdir(exist_ok=True)
    print('2/7 launcher', flush=True)
    build_launcher(stage)
    base = base_python(options.python)
    print('3/7 private CPython from %s' % base.name, flush=True)
    target = stage / 'runtime' / 'python'
    python_version = copy_python(base, target)
    python = target / 'Scripts' / 'python.exe'
    print('4/7 packages', flush=True)
    install_packages(python, stage / 'app' / 'requirements.txt', constraints(output))
    tidy_python(target)
    rows = third_party(python, target, python_version)
    tidy_python(target)
    print('5/7 checks', flush=True)
    seen = check_isolation(stage, python)
    tidy_python(target)
    check_no_build_paths(stage, base)
    (stage / 'runtime' / 'build-info.json').write_text(json.dumps({
        'tool': NAME, 'version': version, 'commit': commit, 'python': python_version,
        'runtimeAbi': release.get('runtime_abi'), 'platform': 'windows-x64',
        'packages': {name: package_version for name, package_version, _ in rows}},
        indent=2) + '\n', encoding='utf-8')

    print('6/7 archives', flush=True)
    portable = output / ('%s-%s-windows-x64.zip' % (NAME, version))
    archive(stage, portable, NAME)
    application = output / 'cytools-app.zip'
    archive(stage / 'app', application, 'app')
    sums = output / 'SHA256SUMS.txt'
    sums.write_text(''.join('%s  %s\n' % (sha256(path), path.name) for path in (portable, application)),
                    encoding='ascii')
    print('7/7 done in %.0f s' % (time.time() - started), flush=True)
    print(json.dumps({'version': version, 'commit': commit, 'python': python_version,
                      'packages': len(rows), 'userSite': seen['userSite'],
                      'files': {path.name: {'bytes': path.stat().st_size, 'sha256': sha256(path)}
                                for path in (portable, application)},
                      'folder': str(output)}, indent=1))


if __name__ == '__main__':
    main()
