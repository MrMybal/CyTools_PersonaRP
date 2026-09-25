"""Stable locations of the Tool's app/data/runtime folders. No side effects on import."""
from pathlib import Path
import json
import os
import sys
import uuid

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
DATA = ROOT / 'data'
RUNTIME = ROOT / 'runtime'

TOOL_ID = 'cy.tool.personarp'



def _location(variable, default):
    """A folder the person may place elsewhere — a Google Drive on Colab, a larger disk.

    Only an absolute path is accepted: a relative one would depend on the directory the Tool
    happens to be started from.
    """
    chosen = os.environ.get(variable, '').strip()
    if chosen and Path(chosen).is_absolute():
        return Path(chosen)
    return default


INPUTS = DATA / 'inputs'
# PERSONARP_MODELS_DIR: the weights live elsewhere (read and written there, receipts included).
MODELS = _location('PERSONARP_MODELS_DIR', DATA / 'models')
LLM_MODELS = MODELS / 'llm'
STT_MODELS = MODELS / 'stt'
TTS_MODELS = MODELS / 'tts'
JOBS = DATA / 'jobs'
SETTINGS = DATA / 'settings'
LOGS = DATA / 'logs'
REPORTS = DATA / 'reports'
EXPORTS = DATA / 'exports'

# The persistent library: this is what makes a character survive a session.
PERSONAS = DATA / 'personas'
WORLDS = DATA / 'worlds'
VOICES = DATA / 'voices'
SESSIONS = DATA / 'sessions'
# Voice batches: each one a folder with its source list and every take it produced.
# PERSONARP_BATCHES_DIR: written elsewhere, so a task survives the machine that ran it.
BATCHES = _location('PERSONARP_BATCHES_DIR', DATA / 'batches')

ENGINES = RUNTIME / 'engines'
DOWNLOADS = RUNTIME / 'downloads'
UPDATES = RUNTIME / 'updates'
BACKUPS = RUNTIME / 'backups'

_LAYOUT = (INPUTS, MODELS, LLM_MODELS, STT_MODELS, TTS_MODELS, JOBS, SETTINGS,
           LOGS, REPORTS, EXPORTS, PERSONAS, WORLDS, VOICES, SESSIONS, BATCHES)


def ensure_data_layout():
    for folder in _LAYOUT:
        folder.mkdir(parents=True, exist_ok=True)


def base_python():
    """Interpreter of the light application environment (runtime/python)."""
    if os.name == 'nt':
        candidate = RUNTIME / 'python' / 'Scripts' / 'python.exe'
    else:
        candidate = RUNTIME / 'python' / 'bin' / 'python'
    return candidate if candidate.exists() else Path(sys.executable)


def engine_python(name):
    """Interpreter of a heavy engine environment (runtime/engines/<name>)."""
    root = ENGINES / name
    if os.name == 'nt':
        return root / 'Scripts' / 'python.exe'
    return root / 'bin' / 'python'


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text('utf-8'))
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, value):
    """Atomic write: a crash mid-save must never truncate a character sheet."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
