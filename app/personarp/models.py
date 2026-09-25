"""Conversation models: catalogue, installation state, download and the llama.cpp engine.

Weights live under data/models/llm/<id>/. An installation receipt sits next to each file and
records the pinned revision, size and SHA-256, so "installed" always means verified rather
than "a folder exists". Receipts carry no absolute path, which is what allows the whole
model tree to be relocated without rewriting anything.
"""
import hashlib
import os
import subprocess
import time
from pathlib import Path

from cytools_core import CyToolError
from cytools_core.downloads import DownloadManager

from .paths import APP, DATA, LLM_MODELS, ROOT, RUNTIME, SETTINGS, read_json, write_json

CATALOG = APP / 'llm-catalog.json'


def catalog():
    return read_json(CATALOG)


def entry(model):
    info = catalog().get(model)
    if not info:
        raise CyToolError('NotFound', 'Unknown conversation model: ' + str(model))
    return info


def directory(model):
    if model not in catalog():
        raise CyToolError('NotFound', 'Unknown conversation model: ' + str(model))
    return LLM_MODELS / model


def model_path(model):
    info = entry(model)
    return directory(model) / info.get('generatedFile', info['files'][0]['name'])


def projector_path(model):
    """The multimodal projector of a vision model, or None for a text-only one."""
    info = catalog().get(model) or {}
    name = info.get('mmproj')
    if not name:
        return None
    path = directory(model) / name
    return path if path.is_file() else None


def is_vision(model):
    return bool((catalog().get(model) or {}).get('vision'))


def vision_models(installed_only=True):
    return [model for model, info in catalog().items()
            if info.get('vision') and (not installed_only or installed(model))]


def sha(path, context=None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            if context:
                context.cancellation.check()
            digest.update(chunk)
    return digest.hexdigest()


def installed(model, verify=False, context=None):
    info = catalog().get(model)
    if not info:
        return False
    for item in info['files']:
        path = directory(model) / item['name']
        receipt = read_json(path.with_name(path.name + '.installed.json'))
        if not path.is_file() or path.stat().st_size != item['size']:
            return False
        if receipt.get('actualSha256') != item['sha256']:
            return False
        if verify and sha(path, context) != item['sha256']:
            return False
    if info.get('generatedFile'):
        from .derived import derived_status
        return derived_status(model, verify, context)
    return True


def status(model, verify=False, context=None):
    info = entry(model)
    present = 0
    for item in info['files']:
        path = directory(model) / item['name']
        if path.is_file():
            present += path.stat().st_size
    return {
        'id': model, 'name': info['name'], 'installed': installed(model, verify, context),
        'sizeBytes': sum(f['size'] for f in info['files']), 'presentBytes': present,
        'license': info.get('license', ''), 'source': info.get('page', ''),
        'revision': info.get('revision', ''), 'ramGiB': info.get('ramGiB', 8),
        'vramGiB': info.get('vramGiB', 6), 'notes': info.get('notes', ''),
        'baseModel': info.get('baseModel', ''),
        'vision': bool(info.get('vision')), 'mmproj': info.get('mmproj', ''),
        'licenseAccepted': bool(read_json(SETTINGS / ('license-llm-' + model + '.json')).get('accepted')),
    }


def catalog_status(verify=False, context=None):
    return [status(model, verify, context) for model in catalog()]


def install(context, parameters):
    model = parameters['model']
    info = entry(model)
    if not parameters.get('accept_license'):
        raise CyToolError('LicenseAcceptanceRequired',
                          'Accept the model licence personally before downloading.',
                          details={'model': model, 'license': info.get('license', ''),
                                   'source': info.get('page', '')})
    if info.get('baseModel') and not installed(info['baseModel']):
        install(context, {'model': info['baseModel'], 'accept_license': True})
    total = sum(f['size'] for f in info['files'])
    done = 0
    for item in info['files']:
        DownloadManager(directory(model)).download(
            item['name'],
            'https://huggingface.co/%s/resolve/%s/%s' % (info['repo'], info['revision'], item['name']),
            sha256=item['sha256'], size=item['size'], revision=info['revision'],
            cancellation=context.cancellation,
            progress=lambda n, t, base=done: context.progress(
                min(99, 100 * (base + n) / total), currentStep='Downloading ' + info['name']))
        done += item['size']
    if info.get('generatedFile'):
        from .derived import prepare
        prepare(model, context)
    if not installed(model, True, context):
        raise CyToolError('IntegrityFailure', 'Model checksum verification failed.')
    write_json(SETTINGS / ('license-llm-' + model + '.json'),
               {'accepted': True, 'license': info.get('license', ''), 'revision': info['revision']})
    return {'model': model, 'installed': True, 'sizeBytes': total}


def installation_resources(model):
    info = entry(model)
    size = sum(f['size'] for f in info['files'])
    base = catalog().get(info.get('baseModel'), {})
    base_size = sum(f['size'] for f in base.get('files', []))
    return {'ramBytes': (4 * 1024 ** 3 if base else 64 * 1024 ** 2), 'cpuThreads': 1,
            'diskBytes': 2 * size + 2 * base_size + 3 * 1024 ** 3}


# --------------------------------------------------------------------------- engine

def engine_path():
    """CPU llama.cpp build. Kept inside runtime/ so an update can never point outside it."""
    info = read_json(SETTINGS / 'engine.json')
    relative = info.get('path', 'runtime/engines/b11057/llama-completion.exe'
                        if os.name == 'nt' else 'runtime/engines/b11057/llama-completion')
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(RUNTIME.resolve()):
        raise CyToolError('InvalidParameters', 'Engine path escapes runtime/.')
    return path


def server_path(device):
    if device == 'cpu':
        return engine_path().with_name('llama-server.exe' if os.name == 'nt' else 'llama-server')
    value = read_json(SETTINGS / 'cuda-engine.json').get('path', '')
    if not value:
        raise CyToolError('MissingDependency', 'Install the CUDA engine in Models.')
    path = (ROOT / value).resolve()
    if not path.is_relative_to(RUNTIME.resolve()) or not path.is_file():
        raise CyToolError('MissingDependency', 'The CUDA engine is missing.')
    return path


def engine_status():
    cuda = read_json(SETTINGS / 'cuda-engine.json')
    cpu_ok = False
    try:
        cpu_ok = engine_path().is_file()
    except CyToolError:
        cpu_ok = False
    cuda_path = ''
    if cuda.get('path'):
        cuda_path = str((ROOT / cuda['path']).resolve())
    return {'cpu': {'installed': cpu_ok, 'path': str(engine_path()) if cpu_ok else ''},
            'cuda': {'installed': bool(cuda_path) and Path(cuda_path).is_file(),
                     'path': cuda_path, 'version': cuda.get('version', ''),
                     'devices': cuda.get('devices', '')}}


def install_cuda(context, parameters):
    from .maintenance import safe_extract
    if os.name != 'nt':
        raise CyToolError('UnsupportedPlatform', 'This CUDA package is built for Windows x64.')
    assets = read_json(APP / 'cuda-assets.json')
    target = RUNTIME / 'engines' / ('b11057-cuda-' + str(time.time_ns()))
    target.mkdir(parents=True)
    for item in assets:
        receipt = DownloadManager(RUNTIME / 'downloads/cuda').download(
            item['name'], item['browser_download_url'],
            sha256=item['digest'].removeprefix('sha256:'), size=item['size'],
            cancellation=context.cancellation,
            progress=lambda n, t: context.progress(min(90, n * 90 / max(t, 1)),
                                                   currentStep='Installing the CUDA engine'))
        context.cancellation.check()
        safe_extract(receipt['path'], target)
    found = list(target.rglob('llama-server.exe'))
    if len(found) != 1:
        raise CyToolError('MissingDependency', 'CUDA server executable missing from the package.')
    path = found[0]
    tested = subprocess.run([str(path), '--list-devices'], capture_output=True, text=True,
                            encoding='utf-8', timeout=40, creationflags=0x08000000)
    if tested.returncode or 'CUDA' not in tested.stdout + tested.stderr:
        raise CyToolError('MissingGPU', 'No compatible CUDA device detected.')
    write_json(SETTINGS / 'cuda-engine.json',
               {'path': str(path.relative_to(ROOT)), 'version': 'b11057', 'sha256': sha(path),
                'devices': tested.stdout + tested.stderr})
    return {'installed': True, 'version': 'b11057', 'devices': tested.stdout + tested.stderr}


def disk_free():
    import shutil
    return shutil.disk_usage(DATA).free
