"""A model download cancelled half way resumes where it stopped, and is verified whole.

The installation goes through the Tool's real install_llm operation and the SDK's real
downloader, over real HTTP: a local server stands in for Hugging Face, serves the file slowly
in pieces, honours Range requests, and records what it was asked. Only the address changes —
the downloader accepts plain HTTP to 127.0.0.1 in its test mode, never for a real source.
"""
import hashlib
import http.server
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import tool                                                                 # noqa: E402
from personarp import locks, models                                         # noqa: E402

SIZE = 3 * 1024 * 1024
PAYLOAD = os.urandom(SIZE)
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
PIECE = 64 * 1024


class Source(http.server.BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        wanted = self.headers.get('Range', '')
        start = int(wanted.split('=')[1].split('-')[0]) if wanted.startswith('bytes=') else 0
        Source.requests.append({'path': self.path, 'range': wanted, 'start': start})
        body = PAYLOAD[start:]
        self.send_response(206 if start else 200)
        if start:
            self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, SIZE - 1, SIZE))
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('ETag', '"%s"' % DIGEST[:16])
        self.end_headers()
        try:
            for offset in range(0, len(body), PIECE):
                self.wfile.write(body[offset:offset + PIECE])
                self.wfile.flush()
                time.sleep(0.01)                   # slow enough to be cancelled half way
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


@pytest.fixture()
def source(tmp_path, monkeypatch):
    Source.requests = []
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Source)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    address = 'http://127.0.0.1:%d' % server.server_address[1]

    real = models.DownloadManager

    class LocalSource(real):
        """The real downloader, pointed at the local server instead of huggingface.co."""
        def __init__(self, root, **options):
            super().__init__(root, allow_test_http=True, **options)

        def download(self, name, url, **options):
            return super().download(name, url.replace('https://huggingface.co', address),
                                    **options)

    catalog = {'test-model': {'name': 'Test model', 'repo': 'nobody/test', 'revision': 'abc123',
                              'license': 'apache-2.0', 'page': 'https://example.org',
                              'files': [{'name': 'model.gguf', 'size': SIZE, 'sha256': DIGEST}]}}
    monkeypatch.setattr(models, 'DownloadManager', LocalSource)
    monkeypatch.setattr(models, 'catalog', lambda: catalog)
    monkeypatch.setattr(models, 'LLM_MODELS', tmp_path / 'models')
    monkeypatch.setattr(models, 'SETTINGS', tmp_path / 'settings')
    monkeypatch.setattr(locks, 'SETTINGS', tmp_path / 'settings')
    monkeypatch.setattr(tool.ResidentModel, 'stop', lambda self: None)
    yield tmp_path / 'models' / 'test-model'
    server.shutdown()
    server.server_close()


def test_a_cancelled_download_resumes_and_is_verified_whole(source):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        actor = runtime.authenticate(runtime.create_client('Test', ['network'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        request = {'model': 'test-model', 'accept_license': True}

        first = runtime.submit(actor, session, 'install_llm', request)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            partial = source / 'model.gguf.part'
            if partial.is_file() and partial.stat().st_size > SIZE // 3:
                break
            time.sleep(0.02)
        runtime.cancel(actor, first['jobId'])
        stopped = runtime.wait(actor, first['jobId'], timeout=30)
        assert stopped['state'] == 'Cancelled', stopped.get('error')
        kept = (source / 'model.gguf.part').stat().st_size
        assert 0 < kept < SIZE and not (source / 'model.gguf').exists()

        second = runtime.wait(actor, runtime.submit(actor, session, 'install_llm',
                                                    request)['jobId'], timeout=60)
    assert second['state'] == 'Completed', second.get('error')
    assert (source / 'model.gguf').read_bytes() == PAYLOAD
    assert models.installed('test-model', verify=True)
    resumed = Source.requests[-1]
    assert resumed['start'] > 0 and resumed['range'] == 'bytes=%d-' % resumed['start']
    assert resumed["start"] <= kept                   # asked only for what was missing
    print("kept %d of %d bytes at cancellation; resumed from byte %d; requests %s" % (
        kept, SIZE, resumed["start"], [r["range"] or "whole" for r in Source.requests]))
