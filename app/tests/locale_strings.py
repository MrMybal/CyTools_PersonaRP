"""Find every piece of interface text in the window's code, the way the window shows it.

The window translates text in three ways, and each leaves a different trace in the source:

  * the ImGui facade (`imgui.button('Save')`, `imgui.text('…')`) translates its label itself;
  * the shared widgets (`widgets.combo(branch, key, 'Label', choices, captions)`) pass their
    label and captions through the facade or through `tr()`;
  * everything else is wrapped in `tr('…')` by hand.

This module reads the code with `ast` and returns the literal strings reaching one of those
three paths, plus the places where text reaches the screen with no way of being translated:
a literal handed straight to the raw ImGui module, or a label built by concatenation or
formatting before it is translated — the catalogue can never hold such a string.

Run it directly to list what the catalogue is missing:
    runtime/python/Scripts/python.exe app/tests/locale_strings.py
"""
import ast
import json
import re
import sys
import unicodedata
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
FILES = sorted((APP / 'gui').glob('*.py')) + [APP / 'desktop.py']
# The progress bar shows the step a job reports, through tr(); these files report steps.
RUNTIME_FILES = [APP / 'tool.py'] + sorted((APP / 'personarp').rglob('*.py')) \
    + sorted((APP / 'workers').glob('*.py'))
# Job states the header shows, as the SDK names them.
JOB_STATES = ['Queued', 'Running', 'Completed', 'Failed', 'Cancelled', 'Cancelling', 'waiting']
# Shown as they are on purpose: the product name.
AS_IS = {'PersonaRP'}
FORMAT = re.compile(r'%[-+ #0-9.]*[sdifr%]')

# The facade translates the first argument of these (see ui_common.ImGuiFacade).
FACADE_LABELS = {'button', 'small_button', 'checkbox', 'radio_button', 'input_text',
                 'input_text_multiline', 'input_int', 'input_float', 'input_double',
                 'slider_int', 'slider_float', 'drag_int', 'drag_float', 'combo', 'begin_combo',
                 'selectable', 'collapsing_header', 'tree_node', 'tree_node_ex',
                 'begin_tab_item', 'menu_item', 'begin_menu'}
FACADE_TEXTS = {'text', 'text_wrapped', 'text_disabled', 'text_unformatted', 'set_tooltip',
                'bullet_text', 'separator_text'}
# Raw ImGui calls that put their argument on screen untranslated.
RAW_TEXTS = FACADE_TEXTS | {'text_colored'} | FACADE_LABELS

# widgets.<name>: positions of the arguments that are shown, and of caption lists.
WIDGET_LABELS = {'text_field': [2], 'multiline': [2], 'string_list': [2, 3],
                 'slider_float': [2], 'slider_int': [2], 'checkbox': [2], 'combo': [2],
                 'picker': [0, 3], 'dictionary_list': [2], 'button': [0], 'small_button': [0]}
# combo(branch, key, label, choices, captions): the choices are shown only without captions.
WIDGET_LISTS = {'combo': 3}
# Local helpers that put their argument on screen through the facade.
DISPLAY_HELPERS = {'tab'}


def visible(text):
    """What the facade looks up: the part before '###' or '##'."""
    head, separator, _ = text.partition('###')
    return head if separator else text.partition('##')[0]


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text)
                   if not unicodedata.combining(c)).replace('’', "'").casefold()


def _callee(node):
    """('imgui'|'raw'|'widgets'|'tr'|'', function name)."""
    function = node.func
    if isinstance(function, ast.Name):
        return ('tr', 'tr') if function.id == 'tr' else ('', function.id)
    if isinstance(function, ast.Attribute):
        owner = function.value
        if isinstance(owner, ast.Name) and owner.id in ('imgui', 'widgets'):
            return owner.id, function.attr
        if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) \
                and owner.func.id == 'raw':
            return 'raw', function.attr
    return '', ''


def _constant(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def wordy(text):
    """Does this carry words once the format placeholders are gone?"""
    return any(character.isalpha() for character in FORMAT.sub('', visible(text or '')))


def _displayed_names(nodes):
    """Names handed to tr(), to the facade or to a widget label inside these nodes."""
    names = set()
    for root in nodes:
        for node in ast.walk(root):
            if not isinstance(node, ast.Call):
                continue
            owner, name = _callee(node)
            positions = []
            if owner == 'tr' or (owner == '' and name in DISPLAY_HELPERS):
                positions = [0]
            elif owner == 'imgui' and (name in FACADE_LABELS or name in FACADE_TEXTS):
                positions = [0]
            elif owner == 'widgets' and name in WIDGET_LABELS:
                positions = WIDGET_LABELS[name]
            for index in positions:
                if index < len(node.args):
                    argument = node.args[index]
                    if isinstance(argument, ast.BinOp):
                        argument = argument.left
                    if isinstance(argument, ast.Call) and _callee(argument)[0] == 'tr' \
                            and argument.args:
                        argument = argument.args[0]
                    if isinstance(argument, ast.Name):
                        names.add(argument.id)
    return names


def _targets(target):
    """Loop target as a list of names (None where the position is not a plain name)."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [element.id if isinstance(element, ast.Name) else None for element in target.elts]
    return []


class Finder(ast.NodeVisitor):
    def __init__(self, path, constants=None):
        self.path = path
        self.strings = {}          # text -> first "file:line"
        self.untranslatable = []   # (where, why, source)
        self.constants = constants or {}

    def looped(self, target, iterable, body):
        """Literal rows a loop hands, element by element, to something that shows them."""
        if isinstance(iterable, ast.Name):
            iterable = self.constants.get(iterable.id)
        if not isinstance(iterable, (ast.List, ast.Tuple)):
            return
        names = _targets(target)
        shown = _displayed_names(body)
        positions = [index for index, name in enumerate(names) if name in shown]
        if not positions:
            return
        for row in iterable.elts:
            if len(names) == 1:
                self.keep(_constant(row), row)
            elif isinstance(row, (ast.Tuple, ast.List)):
                for index in positions:
                    if index < len(row.elts):
                        self.keep(_constant(row.elts[index]), row)

    def visit_For(self, node):
        self.looped(node.target, node.iter, node.body)
        self.generic_visit(node)

    def visit_ListComp(self, node):
        for generator in node.generators:
            self.looped(generator.target, generator.iter, [node.elt])
        self.generic_visit(node)

    visit_GeneratorExp = visit_ListComp

    def keep(self, text, node):
        if text is None:
            return
        text = visible(text)
        if text.strip() and wordy(text) and text not in AS_IS:
            self.strings.setdefault(text, '%s:%d' % (self.path.name, node.lineno))

    def flag(self, node, why):
        self.untranslatable.append(('%s:%d' % (self.path.name, node.lineno), why,
                                    ast.unparse(node)[:120]))

    def shown(self, node, translated_here):
        """An argument that reaches the screen. translated_here: the call translates it."""
        if isinstance(node, ast.IfExp):                 # 'Pause' if playing else 'Play'
            self.shown(node.body, translated_here)
            self.shown(node.orelse, translated_here)
            return
        text = _constant(node)
        if text is not None:
            if translated_here:
                self.keep(text, node)
            elif wordy(text) and visible(text) not in AS_IS:
                self.flag(node, 'literal shown without translation')
            return
        if isinstance(node, ast.Call) and _callee(node)[0] == 'tr':
            return                               # handled when the tr() call is visited
        if isinstance(node, ast.BinOp) and translated_here:
            left = _constant(node.left)
            if left is not None and '##' in left:
                self.keep(left, node)                   # 'Add##' + key: 'Add' is looked up
            elif left is not None and wordy(left):
                self.flag(node, 'built before translation — the catalogue cannot hold it')
        if isinstance(node, ast.JoinedStr) and translated_here:
            self.flag(node, 'f-string label — the catalogue cannot hold it')

    def visit_Assign(self, node):
        """app.notice = '…' is shown by the header through tr()."""
        self.notice(node.targets, node.value, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.notice([node.target], node.value, node)
        self.generic_visit(node)

    def notice(self, targets, value, node):
        if not any(isinstance(target, ast.Attribute) and target.attr == 'notice'
                   for target in targets):
            return
        for part in ([value.body, value.orelse] if isinstance(value, ast.IfExp) else [value]):
            text = _constant(part)
            if text is not None:
                self.keep(text, node)
            elif isinstance(part, ast.BinOp) and _constant(part.left) is not None \
                    and wordy(_constant(part.left)):
                left = _constant(part.left)
                if isinstance(part.op, ast.Add) and len(left) >= 8 \
                        and left.endswith((' ', ': ')):
                    self.keep(left, node)                      # translated as a prefix
                else:
                    self.flag(node, 'notice built before translation')

    def visit_Call(self, node):
        owner, name = _callee(node)
        arguments = node.args
        if owner == '' and name in ('button', 'small_button'):
            owner = 'widgets'                   # inside widgets.py they are called bare
        if owner == 'tr' and arguments:
            text = _constant(arguments[0])
            if text is not None:
                self.keep(text, node)
            elif isinstance(arguments[0], ast.BinOp) and _constant(arguments[0].left):
                self.flag(node, 'tr() of a built string')
        elif owner == 'imgui' and arguments:
            if name in FACADE_LABELS or name in FACADE_TEXTS:
                self.shown(arguments[0], True)
            elif name == 'text_colored' and len(arguments) > 1:
                self.shown(arguments[1], False)
        elif owner == 'raw' and name in RAW_TEXTS and arguments:
            index = 1 if name == 'text_colored' else 0
            if len(arguments) > index:
                self.shown(arguments[index], False)
        elif owner == 'widgets' and name in WIDGET_LABELS:
            for index in WIDGET_LABELS[name]:
                if index < len(arguments):
                    self.shown(arguments[index], True)
            index = WIDGET_LISTS.get(name)
            if index is not None:
                shown = arguments[index + 1] if len(arguments) > index + 1 else \
                    (arguments[index] if len(arguments) > index else None)
                if isinstance(shown, ast.Name):
                    shown = self.constants.get(shown.id)
                if isinstance(shown, (ast.List, ast.Tuple)):
                    for element in shown.elts:
                        self.keep(_constant(element), element)
            if name == 'dictionary_list' and len(arguments) > 3 \
                    and isinstance(arguments[3], (ast.List, ast.Tuple)):
                for field in arguments[3].elts:
                    if isinstance(field, ast.Tuple) and len(field.elts) > 1:
                        self.keep(_constant(field.elts[1]), field)
        self.generic_visit(node)


def steps(files=RUNTIME_FILES):
    """The progress steps jobs report. A formatted step is looked up by its prefix."""
    found, untranslatable = {}, []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'), str(path))):
            if not isinstance(node, ast.keyword) or node.arg not in ('currentStep', 'step'):
                continue
            text = _constant(node.value)
            built = False
            if text is None and isinstance(node.value, ast.BinOp):
                text, built = _constant(node.value.left), True
            if not text or not wordy(text):
                continue
            if '%' in text or built:
                text = text.split('%')[0]
                if len(text) < 8 or not text.endswith(' '):
                    untranslatable.append(('%s:%d' % (path.name, node.value.lineno),
                                           'formatted step without a usable prefix', text))
                    continue
            found.setdefault(text, '%s:%d' % (path.name, node.value.lineno))
    return found, untranslatable


def scan(files=FILES):
    strings, untranslatable = {}, []
    for path in files:
        tree = ast.parse(path.read_text(encoding='utf-8'), str(path))
        constants = {target.id: statement.value for statement in tree.body
                     if isinstance(statement, ast.Assign)
                     for target in statement.targets if isinstance(target, ast.Name)}
        finder = Finder(path, constants)
        finder.visit(tree)
        # By convention a module-level *_CAPTIONS constant holds text the window shows.
        for name, value in constants.items():
            if name.endswith('CAPTIONS') and isinstance(value, (ast.List, ast.Tuple, ast.Dict)):
                for element in (value.values if isinstance(value, ast.Dict) else value.elts):
                    finder.keep(_constant(element), element)
        for text, where in finder.strings.items():
            strings.setdefault(text, where)
        untranslatable += finder.untranslatable
    if files is FILES:
        found, flagged = steps()
        for text, where in found.items():
            strings.setdefault(text, where)
        untranslatable += flagged
        for state in JOB_STATES:
            strings.setdefault(state, 'job state')
    return strings, untranslatable


def catalogue():
    return json.loads((APP / 'locales' / 'ui.json').read_text(encoding='utf-8'))


def missing(strings, entries=None):
    """Strings with no French entry, looked up the way ui_common.tr looks them up."""
    entries = entries if entries is not None else catalogue()
    folded = {normalized(key): value for key, value in entries.items()}
    prefixes = [key for key in entries if len(key) >= 8 and key.endswith((' ', ': '))]
    absent = {}
    for text, where in strings.items():
        entry = entries.get(text) or folded.get(normalized(text))
        if entry and entry.get('fr'):
            continue
        if any(text.startswith(prefix) and text != prefix for prefix in prefixes):
            continue
        absent[text] = where
    return absent


def translate(text, language='fr', entries=None):
    """ui_common.tr, reproduced without importing the window."""
    entries = entries if entries is not None else catalogue()
    folded = {normalized(key): value for key, value in entries.items()}
    prefixes = sorted((key for key in entries if len(key) >= 8 and key.endswith((' ', ': '))),
                      key=len, reverse=True)

    def once(value):
        entry = entries.get(value) or folded.get(normalized(value))
        if entry:
            return entry.get(language, entry.get('en', value))
        if not value.lstrip().startswith(('{', '[')):
            for prefix in prefixes:
                if value.startswith(prefix):
                    return entries[prefix].get(language, prefix) + once(value[len(prefix):])
        return value
    return once(text)


def unstable(strings, language='fr', entries=None):
    """Strings whose translation changes when it is translated again.

    The facade translates labels the code has often translated already; an older entry
    whose French lost its accents then brings "Peripherique" back over "Périphérique".
    """
    entries = entries if entries is not None else catalogue()
    changed = []
    for text in strings:
        first = translate(text, language, entries)
        second = translate(first, language, entries)
        if first != second:
            changed.append((text, first, second))
    return changed


if __name__ == '__main__':
    found, flagged = scan()
    absent = missing(found)
    print('%d strings, %d without French, %d untranslatable sites'
          % (len(found), len(absent), len(flagged)))
    if '--json' in sys.argv:
        print(json.dumps({'missing': absent, 'untranslatable': flagged}, ensure_ascii=False,
                         indent=1))
    else:
        for text, where in sorted(absent.items(), key=lambda item: item[1]):
            print('MISSING  %-24s %r' % (where, text))
        for where, why, source in flagged:
            print('FLAG     %-24s %s: %s' % (where, why, source))
