"""Cross-process locks shared by inference, model installation and update activation.

Two Tool processes (the desktop window and an MCP client, say) must not load two copies of
the same weights or rewrite the application while a scene is being generated: across
processes, a second holder is refused at once with Busy.

Within one process the runtime runs jobs concurrently, so that reading a list or saving a
sheet never waits behind a generation (the window waits for those answers; queued behind a
voice, it stopped drawing and Windows declared it hung). Jobs that need the execution lock
therefore take turns inside the process instead of failing: first come, first served,
cancellable while they wait. A job that already holds the lock may take it again (a
maintenance wrapper around an operation that locks by itself).
"""
import collections
import contextlib
import os
import threading

from cytools_core import CyToolError

from .paths import SETTINGS

WAITING = 'Waiting for the task in progress'


class _Turns:
    """The jobs of this process that want one lock, in the order they asked for it."""

    def __init__(self):
        self.condition = threading.Condition()
        self.queue = collections.deque()
        self.owner = None                       # the thread holding the turn

    def wait(self, context):
        ticket = object()
        with self.condition:
            self.queue.append(ticket)
        told = False
        try:
            while True:
                with self.condition:
                    if self.queue[0] is ticket:
                        self.owner = threading.get_ident()
                        return ticket
                if not told:
                    context.progress(0, currentStep=WAITING)
                    told = True
                context.cancellation.sleep(0.1)          # raises Cancelled when asked to stop
        except BaseException:
            self.leave(ticket)
            raise

    def leave(self, ticket):
        with self.condition:
            if ticket in self.queue:
                if self.queue[0] is ticket:
                    self.owner = None
                self.queue.remove(ticket)
            self.condition.notify_all()


_TURNS = {'execution': _Turns()}


@contextlib.contextmanager
def _file_lock(name):
    path = SETTINGS / (name + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise CyToolError('Busy', 'Another generation or maintenance task is using this Tool.') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


@contextlib.contextmanager
def exclusive(context=None, name='execution'):
    turns = _TURNS.get(name)
    # Only a job (it has a context to report and cancel through) queues; the resident
    # model's long lease and the launch-time update swap keep the plain lock.
    if turns is None or context is None:
        with _file_lock(name):
            if context:
                context.cancellation.check()
            yield
        return
    if turns.owner == threading.get_ident():
        context.cancellation.check()
        yield
        return
    ticket = turns.wait(context)
    try:
        with _file_lock(name):
            context.cancellation.check()
            yield
    finally:
        turns.leave(ticket)
