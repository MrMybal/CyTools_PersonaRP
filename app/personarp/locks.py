"""Cross-process locks shared by inference, model installation and update activation.

Two Tool processes (the desktop window and an MCP client, say) must not load two copies of
the same weights or rewrite the application while a scene is being generated: across
processes, a second holder is refused at once with Busy.

Within one process the runtime orders these jobs itself: every operation that takes the
execution lock is declared in the SDK's `gpu` exclusion group (SDK 0.10, read from the code by
personarp/exclusion.py), so the runtime keeps the next ones Queued and answers everything
else — lists, sheets, sessions — at once. No queue of our own is kept for that.

A job that already holds a lock may take it again: a maintenance wrapper takes it, then the
operation it wraps does too, in the same thread.
"""
import contextlib
import os
import threading

from cytools_core import CyToolError

from .paths import SETTINGS

_HELD = threading.local()


def _held():
    names = getattr(_HELD, 'names', None)
    if names is None:
        names = _HELD.names = set()
    return names


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
    # The resident model's lease is entered in one job and left in another: never re-entrant.
    reentrant = name == 'execution'
    if reentrant and name in _held():
        if context:
            context.cancellation.check()
        yield
        return
    with _file_lock(name):
        if reentrant:
            _held().add(name)
        try:
            if context:
                context.cancellation.check()
            yield
        finally:
            if reentrant:
                _held().discard(name)
