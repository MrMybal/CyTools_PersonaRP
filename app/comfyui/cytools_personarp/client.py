"""Talking to CyTools PersonaRP from ComfyUI.

The nodes never import the Tool: PersonaRP keeps its own Python, its own models and its own
voice engine, and ComfyUI keeps its own. They meet over the Tool's local API — the CyTools
protocol on http://127.0.0.1:<port>/v1, loopback only, with a bearer token — which the
Tool serves itself (`tool.py serve`). When the API is not answering, this module starts it
with the Tool's private interpreter and stops it again when ComfyUI exits.

The token belongs to a client created by the Tool (`tool.py create-client`), kept in the
Tool's own data/settings folder. It is read from there when needed and sent in a header: it
never goes into a workflow, a node widget, a command line or a log.

Standard library only.
"""
import atexit
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / 'config.json'
DEFAULT_PORT = 8791
PERMISSIONS = ('filesystemExternal', 'network')


class ToolError(RuntimeError):
    """An error the Tool reported, or a reason the Tool cannot be reached."""

    def __init__(self, message, code=''):
        super().__init__(message)
        self.code = code


def settings():
    """config.json, written by the Tool when it installs these nodes."""
    try:
        value = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        value = {}
    root = os.environ.get('PERSONARP_TOOL_ROOT') or value.get('tool_root', '')
    return {'tool_root': root, 'port': int(value.get('port') or DEFAULT_PORT),
            'auto_start': bool(value.get('auto_start', True))}


def tool_root():
    root = Path(settings()['tool_root'] or '')
    if not settings()['tool_root'] or not (root / 'app' / 'tool.py').is_file():
        raise ToolError('CyTools PersonaRP introuvable. Installez ces nodes depuis PersonaRP '
                        '(Bibliothèque > ComfyUI), ou indiquez tool_root dans %s.' % CONFIG,
                        'NotConfigured')
    return root


def tool_python(root):
    candidate = root / 'runtime' / 'python' / ('Scripts/python.exe' if os.name == 'nt'
                                               else 'bin/python')
    if not candidate.is_file():
        raise ToolError('Le Python privé de PersonaRP est absent : %s' % candidate, 'NotConfigured')
    return candidate


class Client:
    """One connection to the Tool, shared by every node of this ComfyUI."""

    def __init__(self):
        self.lock = threading.RLock()
        self.process = None
        self.session = ''
        self.token = ''

    # ------------------------------------------------------------------ plumbing

    @property
    def url(self):
        return 'http://127.0.0.1:%d/v1' % settings()['port']

    def data_dir(self):
        # Its own job store: the desktop window keeps data/jobs, and two runtimes do not
        # share one. Characters, voices and models are the same files for both.
        return tool_root() / 'data' / 'jobs-comfyui'

    def _token(self):
        if self.token:
            return self.token
        root = tool_root()
        stored = root / 'data' / 'settings' / 'comfyui-client.json'
        try:
            record = json.loads(stored.read_text(encoding='utf-8'))
            if record.get('token') and record.get('dataDir') == str(self.data_dir()):
                self.token = record['token']
                return self.token
        except (OSError, ValueError):
            pass
        command = [str(tool_python(root)), str(root / 'app' / 'tool.py'), '--data-dir',
                   str(self.data_dir()), 'create-client', '--name', 'comfyui']
        for permission in PERMISSIONS:
            command += ['--permission', permission]
        finished = subprocess.run(command, capture_output=True, text=True, cwd=str(root),
                                  creationflags=_no_window())
        if finished.returncode != 0:
            raise ToolError("PersonaRP n'a pas pu créer de client pour ComfyUI : "
                            + (finished.stderr or finished.stdout)[-800:], 'NotConfigured')
        self.token = json.loads(finished.stdout.strip().splitlines()[-1])['token']
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_text(json.dumps({'token': self.token, 'dataDir': str(self.data_dir())}),
                          encoding='utf-8')
        try:
            os.chmod(stored, 0o600)
        except OSError:
            pass
        return self.token

    def _post(self, method, params, timeout=30):
        body = json.dumps({'protocolVersion': '1.0', 'id': 1, 'method': method,
                           'params': params}).encode('utf-8')
        request = urllib.request.Request(self.url, data=body, headers={
            'Authorization': 'Bearer ' + self._token(), 'Content-Type': 'application/json'})

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as answer:
                result = json.load(answer)
        except urllib.error.HTTPError as exc:
            try:
                error = json.load(exc).get('error') or {}
            except ValueError:
                error = {}
            if isinstance(error, dict) and error.get('code') == 'AuthenticationRequired':
                self.token = ''
            raise ToolError('PersonaRP a refusé la requête (HTTP %d) : %s'
                            % (exc.code, error.get('message', '') if isinstance(error, dict)
                               else error), 'Transport') from exc
        if 'error' in result:
            error = result['error']
            raise ToolError(error.get('message', 'Error'), error.get('code', ''))
        return result['result']

    def _alive(self):
        # GetCapabilities: tiny, open to every client. (GetRuntimeStatus answers InternalError
        # in CyToolsCore 0.9.0, so it cannot tell a live server from a dead one.)
        try:
            self._post('GetCapabilities', {}, timeout=5)
            return True
        except ToolError as exc:
            if exc.code == 'NotConfigured':
                raise
            return False
        except OSError:
            return False

    def running(self):
        """Is the Tool's server answering? Never starts it, nor creates a client."""
        try:
            if not self.token and not (tool_root() / 'data' / 'settings'
                                       / 'comfyui-client.json').is_file():
                return False
            return self._alive()
        except ToolError:
            return False

    def ensure(self):
        """The API answers, starting the Tool's server when it does not."""
        with self.lock:
            if self._alive():
                return
            if self.process is not None and self.process.poll() is None:
                # Ours is still starting: wait for it rather than start a second one, which
                # would find the job store taken and die.
                self._wait_for(self.process)
                return
            if not settings()['auto_start']:
                raise ToolError('PersonaRP ne répond pas sur %s et auto_start est désactivé.'
                                % self.url, 'Unavailable')
            root = tool_root()
            logs = root / 'data' / 'logs'
            logs.mkdir(parents=True, exist_ok=True)
            log = open(logs / 'comfyui-server.log', 'ab')
            self.process = subprocess.Popen(
                [str(tool_python(root)), str(root / 'app' / 'tool.py'), '--data-dir',
                 str(self.data_dir()), 'serve', '--port', str(settings()['port'])],
                cwd=str(root), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                creationflags=_no_window())
            atexit.register(self.stop)
            self._wait_for(self.process)

    def _wait_for(self, process, seconds=90):
        log = tool_root() / 'data' / 'logs' / 'comfyui-server.log'
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ToolError("Le serveur PersonaRP s'est arrêté au démarrage ; voir %s" % log,
                                'Unavailable')
            if self._alive():
                return
            time.sleep(0.5)
        raise ToolError("Le serveur PersonaRP n'a pas répondu en %d s ; voir %s" % (seconds, log),
                        'Unavailable')

    def stop(self):
        """Stop the server this ComfyUI started — never one started by someone else.

        On Windows the python.exe of a virtual environment is a launcher that starts the real
        interpreter as a child: stopping the launcher alone would leave the server, and the
        voice workers holding the graphics memory, running. The whole tree is stopped.
        """
        process, self.process = self.process, None
        if process is None or process.poll() is not None:
            return
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, creationflags=_no_window())
        else:
            process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()

    # ---------------------------------------------------------------- operations

    def call(self, method, **params):
        self.ensure()
        return self._post(method, params)

    def _session(self):
        if not self.session:
            self.session = self.call('CreateSession', temporary=False)['sessionId']
        return self.session

    def run(self, operation, parameters, progress=None, interrupted=None, timeout=4 * 3600):
        """Submit, follow, return the outputs. `progress(percent, step)` is called as the job
        moves; `interrupted()` returning True cancels it (the Stop button of ComfyUI)."""
        self.ensure()
        try:
            job = self._post('SubmitJob', {'sessionId': self._session(), 'operationId': operation,
                                           'parameters': parameters})
        except ToolError as exc:
            if exc.code not in ('NotFound', 'AccessDenied') or not self.session:
                raise
            self.session = ''                                   # the server was restarted
            job = self._post('SubmitJob', {'sessionId': self._session(), 'operationId': operation,
                                           'parameters': parameters})
        deadline = time.monotonic() + timeout
        last = None
        while job['state'] not in ('Completed', 'Failed', 'Cancelled'):
            if interrupted is not None and interrupted():
                self._post('CancelJob', {'jobId': job['jobId']})
                raise ToolError('Annulé depuis ComfyUI.', 'Cancelled')
            if time.monotonic() > deadline:
                self._post('CancelJob', {'jobId': job['jobId']})
                raise ToolError('%s a dépassé %d s.' % (operation, timeout), 'Timeout')
            time.sleep(0.5)
            job = self._post('GetJob', {'jobId': job['jobId']})
            state = job.get('progress') or {}
            now = (state.get('percent'), state.get('currentStep'))
            if progress is not None and now != last:
                progress(float(state.get('percent') or 0), state.get('currentStep') or '')
                last = now
        if job['state'] != 'Completed':
            error = job.get('error') or {}
            raise ToolError('%s: %s' % (operation, error.get('message', job['state'])),
                            error.get('code', job['state']))
        return job.get('outputs') or {}


def _no_window():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


CLIENT = Client()
