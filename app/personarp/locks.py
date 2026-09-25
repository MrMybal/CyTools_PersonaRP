"""Cross-process locks shared by inference, model installation and update activation.

Two Tool processes (the desktop window and an MCP client, say) must not load two copies of
the same weights or rewrite the application while a scene is being generated.
"""
import contextlib
import os

from cytools_core import CyToolError

from .paths import SETTINGS


@contextlib.contextmanager
def exclusive(context=None, name='execution'):
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
            if context:
                context.cancellation.check()
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
