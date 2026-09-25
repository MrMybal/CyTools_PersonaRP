"""Running the voice workers: one resident process per backend, shared by every interface.

The workers live in the private voice engine, not in the Tool's own environment, so the
heavy stack never loads inside the window or the MCP server. A worker is started on first
use, kept between jobs, and stopped when a job asks for the resources back, when the user
cancels, or after the idle delay.
"""
import os
import sys

from cytools_core import CyToolError

from ..paths import APP, LOGS, ROOT
from ..workerhost import WorkerHost, WorkerPool
from . import catalog

IDLE_SECONDS = 600
POOL = WorkerPool()


def bind(runtime):
    POOL.runtime = runtime
    return POOL


def _environment():
    """The worker imports personarp.voice.annotations from app/, and nothing else of ours."""
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(APP) + os.pathsep + environment.get('PYTHONPATH', '')
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    return environment


def host(name):
    def factory():
        python = catalog.engine_python()
        if not python.is_file():
            raise CyToolError(
                'MissingDependency',
                'The voice engine is not installed. Install it from the Voice tab, or run '
                'app/setup_engine.py voice.')
        return WorkerHost(name, [str(python), str(APP / 'workers' / (name + '_worker.py'))],
                          cwd=str(ROOT), env=_environment(),
                          log_path=LOGS / ('worker-' + name + '.log'),
                          idle_seconds=IDLE_SECONDS, startup_timeout=300)
    return POOL.get(name, factory)


def speak(context, parameters, *, offset=0.0, scale=1.0, timeout=1800):
    """Render a take. The model stays resident so the next line does not reload it."""
    POOL.make_exclusive('tts')
    return host('tts').run_job(context, 'synthesize', parameters, timeout=timeout,
                               progress_offset=offset, progress_scale=scale)


def speak_batch(context, parameters, *, offset=0.0, scale=1.0, timeout=6 * 3600):
    """Many lines in one pass of the model; the worker sizes the batches to the free VRAM."""
    POOL.make_exclusive('tts')
    return host('tts').run_job(context, 'synthesize_batch', parameters, timeout=timeout,
                               progress_offset=offset, progress_scale=scale)


def transcribe(context, parameters, *, offset=0.0, scale=1.0, timeout=900):
    POOL.make_exclusive('stt')
    return host('stt').run_job(context, 'transcribe', parameters, timeout=timeout,
                               progress_offset=offset, progress_scale=scale)


def diagnose(context=None):
    """Report the engine and each worker without starting anything that is not running."""
    report = {'engine': catalog.engine_status(), 'workers': POOL.status()}
    return report


def release():
    POOL.stop_all()
    return {'released': True}
