"""Which operations take the execution lock, read from tool.py itself.

The manifest declares those operations in the SDK's `gpu` exclusion group, so the runtime
queues them one after the other (they stay Queued, take no worker slot, and the window's
reads are never held behind them). The list is computed from the code rather than written by
hand: an operation that starts taking the lock joins the group, and a test compares the
generated manifest with this reading, so the two cannot drift apart.
"""
import ast
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / 'tool.py'
GROUP = 'gpu'


def _takes_execution_lock(function):
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'exclusive':
            names = [keyword.value for keyword in node.keywords if keyword.arg == 'name']
            if len(node.args) < 2 and (not names or (isinstance(names[0], ast.Constant)
                                                     and names[0].value == 'execution')):
                return True
    return False


def locked_operations(source=TOOL):
    """Operation identifiers whose handler (or its wrapper) takes the execution lock."""
    tree = ast.parse(Path(source).read_text(encoding='utf-8'))
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    imported = {'update': 'maintenance.update'}           # handlers living in other modules
    locked = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, 'attr', '') == 'register'
                and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant)):
            continue
        operation, handler = node.args[0].value, node.args[1]
        names = []
        if isinstance(handler, ast.Call):                   # a wrapper around a handler
            names.append(getattr(handler.func, 'id', ''))
            names += [getattr(argument, 'id', getattr(argument, 'attr', ''))
                      for argument in handler.args]
        else:
            names.append(getattr(handler, 'id', getattr(handler, 'attr', '')))
        if any(name in functions and _takes_execution_lock(functions[name]) for name in names):
            locked.add(operation)
        elif any(name in imported for name in names):
            locked.add(operation)
    return sorted(locked)
