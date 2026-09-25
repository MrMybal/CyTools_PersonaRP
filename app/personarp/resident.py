"""An owned llama.cpp server, held between replies when the character asks to stay loaded.

The server is bound to the loopback interface on a random port behind a per-launch bearer
token, and on Windows it is attached to a job object so it cannot outlive the Tool. The SDK
reservation is held for as long as the process really runs, and released only once it has
actually stopped — not when cancellation is requested.
"""
import concurrent.futures
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.request

from cytools_core import CyToolError

from . import models
from .context_window import fit_messages
from .locks import exclusive


class ResidentModel:
    def __init__(self, runtime):
        self.runtime = runtime
        self.process = None
        self.key = None
        self.log = None
        self.lease = None
        self.job_handle = None
        self.token = ''
        self.url = ''
        self.lock = threading.RLock()
        self.worker_id = 'resident-llm'
        runtime.register_worker(self.worker_id, self)

    def health(self):
        with self.lock:
            if self.process and self.process.poll() is not None:
                self.stop()
            return {'loaded': bool(self.process),
                    'pid': self.process.pid if self.process else None,
                    'model': self.key[0] if self.key else '',
                    'device': self.key[1] if self.key else ''}

    def release(self, level):
        if level in ('Model', 'Worker', 'All'):
            self.stop()

    def stop(self):
        with self.lock:
            if self.process:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                self.process = None
            if self.job_handle:
                self.job_handle.Close()
                self.job_handle = None
            if self.log:
                self.log.close()
                self.log = None
            self.key = None
            self.token = ''
            self.runtime.ledger.release('worker:' + self.worker_id)
            if self.lease:
                self.lease.__exit__(None, None, None)
                self.lease = None

    def request(self, path, payload=None, timeout=3):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.url + path, data=body,
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def ensure(self, context, settings):
        """Start the server, or report that the already-loaded one matches. Returns `reused`."""
        model = settings['llm_model']
        path = models.model_path(model)
        if not path.is_file():
            raise CyToolError('MissingModel', 'Install the selected model in Models.')
        projector = models.projector_path(model)
        key = (model, settings['device'], settings['threads'], context.workspace.parent.name,
               str(path), path.stat().st_mtime_ns, str(projector or ''))
        if self.health()['loaded'] and key == self.key:
            return True
        self.stop()
        info = models.entry(model)
        if not models.installed(model, True, context):
            raise CyToolError('MissingModel', 'Install or repair the selected model in Models.')
        executable = models.server_path(settings['device'])
        if not executable.is_file():
            raise CyToolError('MissingDependency', 'llama-server is missing.')
        needs = {'ramBytes': (info.get('ramGiB', 8) if settings['device'] == 'cpu' else 4) * 1024 ** 3,
                 'cpuThreads': 0}
        gpu = ''
        if settings['device'] == 'cuda':
            devices = self.runtime.ledger.capacity.get('vramBytes', {})
            if not devices:
                raise CyToolError('MissingGPU', 'No NVIDIA CUDA GPU found.')
            gpu = max(devices, key=devices.get)
            needs['vramBytes'] = {gpu: info.get('vramGiB', 6) * 1024 ** 3}
        if not self.runtime.reserve_worker(self.worker_id, needs):
            raise CyToolError('InsufficientResources',
                              'Unload other models, pick a smaller one, or switch to CPU.')
        try:
            self.lease = exclusive(name='resident')
            self.lease.__enter__()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            self.token = secrets.token_urlsafe(32)
            self.url = 'http://127.0.0.1:%d' % port
            self.log = context.path('outputs/llama-server.log').open('wb')
            command = [str(executable), '-m', str(path), '--host', '127.0.0.1', '--port', str(port),
                       '-c', '16384', '-t', str(settings['threads']),
                       '-ngl', '999' if settings['device'] == 'cuda' else '0',
                       '-np', '1', '--no-webui', '--no-slots', '--no-cache-prompt']
            if projector is not None:
                # A vision model needs its projector; --no-mmproj-auto keeps the server from
                # fetching one from the internet behind our back.
                command += ['--mmproj', str(projector), '--image-max-tokens', '2048']
            else:
                command.append('--no-mmproj-auto')
            environment = {**os.environ, 'LLAMA_API_KEY': self.token}
            if settings['device'] == 'cuda':
                environment['CUDA_VISIBLE_DEVICES'] = gpu
            self.process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log,
                env=environment, creationflags=0x08000000 if os.name == 'nt' else 0)
            if os.name == 'nt':
                import win32api, win32con, win32job
                self.job_handle = win32job.CreateJobObject(None, '')
                limits = win32job.QueryInformationJobObject(
                    self.job_handle, win32job.JobObjectExtendedLimitInformation)
                limits['BasicLimitInformation']['LimitFlags'] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                win32job.SetInformationJobObject(
                    self.job_handle, win32job.JobObjectExtendedLimitInformation, limits)
                handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, self.process.pid)
                try:
                    win32job.AssignProcessToJobObject(self.job_handle, handle)
                finally:
                    handle.Close()
            self.key = key
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                context.cancellation.check()
                if self.process.poll() is not None:
                    raise CyToolError('WorkerCrashed',
                                      'llama-server stopped. See outputs/llama-server.log in the job.')
                try:
                    if self.request('/health')['status'] == 'ok':
                        return False
                except (OSError, ValueError):
                    pass
                context.cancellation.sleep(.1)
            raise CyToolError('Timeout', 'Loading the model timed out.')
        except BaseException:
            self.stop()
            raise

    def generate(self, context, settings, items, json_schema=None, progress=(5, 15), fit=True):
        """Run one completion. With json_schema the server constrains decoding to that shape,
        which is what makes the scene directive reliable instead of best-effort.

        `fit` is turned off for a multimodal call: the history-fitting pass counts tokens by
        re-templating the messages, which a message carrying an image cannot survive — and a
        single-image request has no history to trim anyway.
        """
        with self.lock:
            start = time.monotonic()
            try:
                context.progress(progress[0],
                                 currentStep='Loading the model / reusing the resident one')
                reused = self.ensure(context, settings)

                def count_tokens(messages):
                    formatted = self.request('/apply-template', {
                        'messages': messages, 'add_generation_prompt': True,
                        'chat_template_kwargs': {'enable_thinking': False}}, timeout=30)['prompt']
                    return len(self.request('/tokenize',
                                            {'content': formatted, 'add_special': True},
                                            timeout=30)['tokens'])

                if fit:
                    items, window = fit_messages(items, count_tokens, settings['response_length'])
                else:
                    window = {'promptTokens': None, 'droppedMessages': 0, 'fitted': False}
                context.progress(progress[1],
                                 currentStep='Generating on ' + settings['device'].upper())
                payload = {'messages': items, 'max_tokens': settings['response_length'],
                           'temperature': settings['temperature'], 'top_p': settings.get('top_p', 0.95),
                           'repeat_penalty': settings.get('repeat_penalty', 1.08),
                           'seed': settings.get('seed', -1), 'stream': False, 'cache_prompt': False,
                           'chat_template_kwargs': {'enable_thinking': False},
                           'reasoning_effort': models.entry(settings['llm_model']).get('reasoningEffort', 'none')}
                if json_schema:
                    payload['json_schema'] = json_schema
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(self.request, '/v1/chat/completions', payload, 900)
                    try:
                        while True:
                            context.cancellation.check()
                            try:
                                response = future.result(timeout=.05)
                                break
                            except concurrent.futures.TimeoutError:
                                continue
                    except BaseException:
                        self.stop()
                        raise
                choice = response['choices'][0]
                text = (choice['message'].get('content') or '').strip()
                if not text:
                    raise CyToolError('EmptyResponse', 'The model returned no text.')
                return {'text': text, 'seconds': round(time.monotonic() - start, 3),
                        'reused': reused, 'pid': self.process.pid, 'window': window,
                        'truncated': choice.get('finish_reason') == 'length',
                        'finishReason': choice.get('finish_reason', '')}
            except BaseException:
                self.stop()
                raise
            finally:
                if not settings.get('keep_loaded'):
                    self.stop()
