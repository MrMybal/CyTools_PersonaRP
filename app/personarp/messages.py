"""The messages an operation sends back, in the language of the window that shows them.

An operation's messages are shared by the window, the CLI and MCP, so they are written in
English, once. The window translates them when it shows them: `locales/messages.json` holds
one entry per message as the code writes it, the variable parts written {0}, {1}… in the order
they appear. A message is matched whole; a variable part that is itself a known message
(a reason followed by what happens next) is translated too.

`templates()` reads the messages straight from the code, which is how the catalogue is kept
complete: a test fails as soon as a message has no translation.
"""
import ast
import json
import re
from functools import lru_cache
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
CATALOG = APP / 'locales' / 'messages.json'
RAISERS = ('CyToolError', 'WorkerError')
# Messages built outside a raise that the window shows as they are.
SHOWN = ('remark', 'note', 'reason', 'error', 'message', 'statusMessage')
SCANNED = ('personarp', 'workers', 'tool.py', 'model_options.py', 'installation_ui.py',
           'setup_engine.py', 'generation_config.py')
PLACEHOLDER = re.compile(r'%(?:\([^)]*\))?[-+ #0]*(?:\d+|\*)?(?:\.\d+)?[sdifgeExXr%]')


def _from_percent(literal):
    """'The voice "%s" is missing.' -> 'The voice "{0}" is missing.'"""
    counter = iter(range(100))
    return PLACEHOLDER.sub(lambda m: '%' if m.group(0) == '%%' else '{%d}' % next(counter), literal)


def _from_parts(parts):
    text, number = '', 0
    for part in parts:
        if isinstance(part, str):
            text += part.replace('{', '{{').replace('}', '}}')
        else:
            text += '{%d}' % number
            number += 1
    return text


def _flatten_add(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten_add(node.left) + _flatten_add(node.right)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return [None]


def template_of(node):
    """The catalogue key for a message expression, or '' when it is not a readable text."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.replace('{', '{{').replace('}', '}}')
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
            and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
        return _from_percent(node.left.value.replace('{', '{{').replace('}', '}}'))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        parts = _flatten_add(node)
        if any(isinstance(part, str) and part.strip() for part in parts):
            return _from_parts(parts)
    if isinstance(node, ast.JoinedStr):
        return _from_parts([value.value if isinstance(value, ast.Constant) else None
                            for value in node.values])
    return ''


def templates(root=APP):
    """Every message the code raises or hands to the window, as catalogue keys."""
    found = {}
    files = []
    for name in SCANNED:
        target = root / name
        files += sorted(target.rglob('*.py')) if target.is_dir() else [target]
    for path in files:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.Call):
                name = getattr(node.func, 'id', getattr(node.func, 'attr', ''))
                owner = getattr(getattr(node.func, 'value', None), 'id', '') or \
                    getattr(getattr(node.func, 'value', None), 'attr', '')
                if name in RAISERS and len(node.args) >= 2:
                    candidates.append(node.args[1])
                elif name == 'remark' and node.args:
                    candidates.append(node.args[0])
                elif name == 'append' and node.args and owner == 'problems' or \
                        name == 'append' and isinstance(getattr(node.func, 'value', None),
                                                        ast.Subscript):
                    candidates.append(node.args[0])
                elif name in ('update',) and node.keywords:
                    candidates += [keyword.value for keyword in node.keywords
                                   if keyword.arg in ('error', 'note')]
            elif isinstance(node, ast.Dict):
                candidates += [value for key, value in zip(node.keys, node.values)
                               if isinstance(key, ast.Constant) and key.value in ('message',
                                                                                  'reason')]
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Subscript) and (
                        isinstance(target.slice, ast.Constant) and target.slice.value in ('error',)
                        or getattr(target.value, 'id', '') == 'duplicates'):
                    candidates.append(node.value)
            elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add) \
                    and getattr(node.target, 'id', '') in ('reason', 'note'):
                tail = template_of(node.value)
                if tail:
                    found.setdefault('{0}' + tail.replace('{0}', '{1}'), '%s:%d' % (
                        path.relative_to(root).as_posix(), node.lineno))
            elif isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
                candidates += list(node.value.elts)
            for candidate in candidates:
                key = template_of(candidate)
                if ' ' in key.strip() and re.search('[A-Za-z]{3}', key):
                    found.setdefault(key, '%s:%d' % (path.relative_to(root).as_posix(),
                                                     node.lineno))
    return found


@lru_cache(maxsize=1)
def catalog():
    try:
        entries = json.loads(CATALOG.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}, []
    patterns = []
    for key, languages in entries.items():
        if '{0}' not in key:
            continue
        pieces = re.split(r'(\{\d+\})', key)
        regex = ''.join('(?P<p%s>.+?)' % piece[1:-1] if re.fullmatch(r'\{\d+\}', piece)
                        else re.escape(piece.replace('{{', '{').replace('}}', '}'))
                        for piece in pieces)
        literal = sum(len(piece) for piece in pieces if not re.fullmatch(r'\{\d+\}', piece))
        patterns.append((literal, re.compile('^' + regex + '$', re.S), languages))
    patterns.sort(key=lambda item: -item[0])       # the most specific message first
    return entries, patterns


def translate(message, language, depth=0):
    """The message in `language`, or the message itself when the catalogue does not know it."""
    if not isinstance(message, str) or not message or language in ('', 'en') or depth > 3:
        return message
    entries, patterns = catalog()
    exact = entries.get(message.replace('{', '{{').replace('}', '}}'))
    if exact and exact.get(language):
        return exact[language].replace('{{', '{').replace('}}', '}')
    for _, pattern, languages in patterns:
        found = pattern.match(message)
        if found and languages.get(language):
            values = {name[1:]: translate(value, language, depth + 1)
                      for name, value in found.groupdict().items()}
            return re.sub(r'\{(\d+)\}', lambda m: values.get(m.group(1), m.group(0)),
                          languages[language]).replace('{{', '{').replace('}}', '}')
    return message


def describe(error, language):
    """What to show for an operation's error: a dict, an exception or a text."""
    if isinstance(error, dict):
        message = error.get('message') or error.get('code') or ''
    else:
        message = str(error or '')
    return translate(message, language)
