"""A generation never freezes the window: what the window waits for is answered at once.

The window asks the runtime for lists, sheets and sessions and waits for the answer. Under a
sequential runtime those requests queued behind a voice being spoken; the window stopped
drawing, Windows declared it hung, and the voice already generated was lost with the process.
The runtime now runs jobs concurrently, and the jobs that need the execution lock take turns
on it inside the process (first come, first served, cancellable while waiting), while another
process is still refused with Busy.

No model here: the job holding the lock is release_voice with the voice runner held on an event.
"""
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from cytools_core import CyToolError                                        # noqa: E402
from cytools_core.runtime import CancellationToken                           # noqa: E402

import tool                                                                 # noqa: E402
from personarp import batches, locks                                        # noqa: E402


@pytest.fixture()
def held(monkeypatch, tmp_path):
    """release_voice blocks until `go` is set, as a voice being spoken holds the lock."""
    state = {'started': threading.Event(), 'go': threading.Event(), 'calls': 0}

    def slow_release():
        state['calls'] += 1
        state['started'].set()
        assert state['go'].wait(20)
        return {'released': True}

    monkeypatch.setattr(tool.voice_runner, 'release', slow_release)
    monkeypatch.setattr(locks, 'SETTINGS', tmp_path / 'settings')
    monkeypatch.setattr(batches, 'BATCHES', tmp_path / 'batches')
    return state


def _client(runtime):
    actor = runtime.authenticate(runtime.create_client('Test', [])['token'])
    return actor, runtime.create_session(actor, temporary=True)['sessionId']


def _state_soon(runtime, actor, job_id, wanted, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = runtime.get_job(actor, job_id)
        if wanted(job):
            return job
        time.sleep(0.05)
    return runtime.get_job(actor, job_id)


def test_the_manifest_lets_light_operations_through():
    manifest = json.loads((APP / 'CyTool.json').read_text(encoding='utf-8'))
    assert manifest['concurrency']['policy'] == 'Concurrent'
    assert manifest['concurrency']['maxWorkers'] >= 8


def test_a_list_is_answered_while_a_voice_holds_the_lock(held):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        actor, session = _client(runtime)
        voice = runtime.submit(actor, session, 'release_voice', {})
        assert held['started'].wait(10)
        began = time.monotonic()
        listed = runtime.wait(actor, runtime.submit(actor, session, 'list_batches', {})['jobId'],
                              timeout=5)
        assert listed['state'] == 'Completed', listed.get('error')
        assert time.monotonic() - began < 3                  # the window's answer, not a queue
        assert runtime.get_job(actor, voice['jobId'])['state'] == 'Running'
        held['go'].set()
        assert runtime.wait(actor, voice['jobId'], timeout=10)['state'] == 'Completed'


def test_a_second_job_needing_the_lock_waits_its_turn(held):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        actor, session = _client(runtime)
        first = runtime.submit(actor, session, 'release_voice', {})
        assert held['started'].wait(10)
        second = runtime.submit(actor, session, 'release_voice', {})
        waiting = _state_soon(runtime, actor, second['jobId'],
                              lambda job: job['progress'].get('currentStep') == locks.WAITING)
        assert waiting['state'] == 'Running' and held['calls'] == 1   # neither Busy nor started
        held['go'].set()
        assert runtime.wait(actor, first['jobId'], timeout=10)['state'] == 'Completed'
        assert runtime.wait(actor, second['jobId'], timeout=10)['state'] == 'Completed'
        assert held['calls'] == 2


def test_a_job_waiting_for_the_lock_can_be_cancelled(held):
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        actor, session = _client(runtime)
        first = runtime.submit(actor, session, 'release_voice', {})
        assert held['started'].wait(10)
        # chat takes the lock on its first line; it is cancelled before it could go further.
        second = runtime.submit(actor, session, 'chat', {'text': 'Bonjour.'})
        _state_soon(runtime, actor, second['jobId'],
                    lambda job: job['progress'].get('currentStep') == locks.WAITING)
        runtime.cancel(actor, second['jobId'])
        assert runtime.wait(actor, second['jobId'], timeout=10)['state'] == 'Cancelled'
        held['go'].set()
        assert runtime.wait(actor, first['jobId'], timeout=10)['state'] == 'Completed'
        assert held['calls'] == 1
        assert not locks._TURNS['execution'].queue                  # nobody left in line


def test_unloading_the_model_waits_for_the_generation(held, monkeypatch):
    stopped = []
    monkeypatch.setattr(tool.ResidentModel, 'stop', lambda self: stopped.append(time.monotonic()))
    with tempfile.TemporaryDirectory() as root, tool.create_runtime(root) as runtime:
        actor, session = _client(runtime)
        voice = runtime.submit(actor, session, 'release_voice', {})
        assert held['started'].wait(10)
        unload = runtime.submit(actor, session, 'unload_model', {})
        time.sleep(0.5)
        assert not stopped                                           # not under the running job
        held['go'].set()
        assert runtime.wait(actor, voice['jobId'], timeout=10)['state'] == 'Completed'
        assert runtime.wait(actor, unload['jobId'], timeout=10)['state'] == 'Completed'
        assert stopped


class _Context:
    def __init__(self):
        self.cancellation = CancellationToken()
        self.steps = []

    def progress(self, percent, **fields):
        self.steps.append(fields.get('currentStep'))


def test_a_holder_may_take_the_lock_again(tmp_path, monkeypatch):
    monkeypatch.setattr(locks, 'SETTINGS', tmp_path)
    context = _Context()
    with locks.exclusive(context):
        with locks.exclusive(context):                               # a wrapper, then its handler
            pass
    assert not locks._TURNS['execution'].queue and locks._TURNS['execution'].owner is None


def test_another_process_is_still_refused_with_busy(tmp_path, monkeypatch):
    monkeypatch.setattr(locks, 'SETTINGS', tmp_path)
    holder = subprocess.Popen(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0, %r)\n'
         'from pathlib import Path\n'
         'from personarp import locks\n'
         'locks.SETTINGS = Path(%r)\n'
         'with locks.exclusive():\n'
         '    print("held", flush=True)\n'
         '    sys.stdin.readline()\n' % (str(APP), str(tmp_path))],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'held'
        with pytest.raises(CyToolError) as refused:
            with locks.exclusive(_Context()):
                pass
        assert refused.value.code == 'Busy'
        assert not locks._TURNS['execution'].queue                   # the refused job left the line
    finally:
        holder.stdin.write('\n')
        holder.stdin.flush()
        holder.wait(10)
