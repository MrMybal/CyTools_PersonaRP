"""Launch entry point: activate a staged application if one is pending, then open the window."""
from pathlib import Path
import runpy, sys, traceback

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'app'))
try:
    from personarp.maintenance import apply_pending_app
    apply_pending_app()
    # Reload after a possible replacement of the application directory.
    for name in [n for n in list(sys.modules) if n == 'personarp' or n.startswith('personarp.')]:
        sys.modules.pop(name, None)
    runpy.run_path(str(root / 'app/desktop.py'), run_name='__main__')
except BaseException:
    (root / 'data/logs').mkdir(parents=True, exist_ok=True)
    (root / 'data/logs/launcher-error.log').write_text(traceback.format_exc(), encoding='utf-8')
    raise
