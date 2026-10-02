"""Resuming a real Hugging Face download, without downloading the whole file.

The SDK downloader is given the exact request the Voice tab makes for a catalogue file (the
Qwen3-TTS speech tokenizer, 650 MB, pinned revision, SHA-256). It is cancelled after about
15 MB, started again, and cancelled once more 15 MB later. On the second start it must ask
for the missing bytes only, and it refuses to continue when the server's Content-Range does
not match what it asked — so a second run that goes on growing the same partial file is a
resume Hugging Face (and the CDN it redirects to) really honoured. About 30 MB of network;
everything goes to a temporary folder that is deleted afterwards.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_download_resume.py
Writes data/reports/download-resume-acceptance.json.
"""
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from cytools_core import CyToolError                                      # noqa: E402
from cytools_core.downloads import DownloadManager                          # noqa: E402
from cytools_core.runtime import CancellationToken                          # noqa: E402

STEP = 15 * 1024 * 1024


def run_until(manager, name, url, info, stop_at):
    token = CancellationToken()
    seen = {'first': None, 'last': 0, 'error': ''}

    def progress(done, total):
        seen['first'] = done if seen['first'] is None else seen['first']
        seen['last'] = done
        if done >= stop_at:
            token.cancel('enough for this step')

    def work():
        try:
            manager.download(name, url, sha256=info['sha256'], size=info['size'],
                             cancellation=token, progress=progress)
        except CyToolError as exc:
            seen['error'] = '%s: %s' % (exc.code, exc)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(600)
    return seen


def main():
    catalog = json.loads((APP / 'tts-catalog.json').read_text(encoding='utf-8'))
    key = 'qwen3tts-0.6b-base'
    info = catalog[key]
    item = next(f for f in info['files'] if f['name'] == 'speech_tokenizer/model.safetensors')
    url = 'https://huggingface.co/%s/resolve/%s/%s' % (info['repo'], info['revision'], item['name'])
    folder = Path(tempfile.mkdtemp(prefix='resume-'))
    name = 'model.safetensors'
    try:
        manager = DownloadManager(folder)
        began = time.time()
        first = run_until(manager, name, url, item, STEP)
        partial = folder / (name + '.part')
        kept = partial.stat().st_size if partial.is_file() else 0
        second = run_until(manager, name, url, item, kept + STEP)
        grown = partial.stat().st_size if partial.is_file() else 0
        metadata = json.loads((folder / (name + '.download.json')).read_text(encoding='utf-8')) \
            if (folder / (name + '.download.json')).is_file() else {}
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    ok = (0 < kept < item['size'] and grown > kept + STEP // 2
          and 'source changed' not in second['error'] and (second['first'] or 0) >= kept)
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'file': '%s/%s@%s' % (
        info['repo'], item['name'], info['revision'][:12]), 'sizeBytes': item['size'],
        'keptAfterFirstCancel': kept, 'secondRunFirstProgress': second['first'],
        'partialAfterSecondCancel': grown, 'firstRun': first, 'secondRun': second,
        'etagKept': bool(metadata.get('etag')), 'seconds': round(time.time() - began, 1),
        'ok': ok}
    output = ROOT / 'data/reports/download-resume-acceptance.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
