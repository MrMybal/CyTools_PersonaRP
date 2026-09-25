"""Small editing widgets shared by the panels.

The character sheet is deep, so these helpers edit a branch of it in place and report
whether anything changed — which is what drives the "unsaved changes" marker.
"""
from ui_common import imgui, raw, tr


def text_field(persona_branch, key, label, width=0.0):
    changed, value = imgui.input_text(label + '##' + key, str(persona_branch.get(key, '')))
    if changed:
        persona_branch[key] = value
    return changed


def multiline(persona_branch, key, label, height=64):
    imgui.text(label)
    changed, value = imgui.input_text_multiline('##' + key, str(persona_branch.get(key, '')),
                                                (-1, height))
    if changed:
        persona_branch[key] = value
    return changed


def string_list(persona_branch, key, label, hint=''):
    """A list of short entries, edited one line per entry."""
    values = list(persona_branch.get(key) or [])
    changed = False
    imgui.push_id(key)
    imgui.text(label)
    if hint:
        imgui.same_line()
        raw().text_disabled('(?)')
        if raw().is_item_hovered():
            raw().set_tooltip(tr(hint))
    removed = -1
    for index, entry in enumerate(values):
        imgui.push_id(index)
        edited, value = imgui.input_text('##entry', str(entry))
        if edited:
            values[index] = value
            changed = True
        imgui.same_line()
        if small_button('-'):
            removed = index
        imgui.pop_id()
    if removed >= 0:
        values.pop(removed)
        changed = True
    if button('Add##' + key):
        values.append('')
        changed = True
    imgui.pop_id()
    if changed:
        persona_branch[key] = values
    return changed


def slider_float(branch, key, label, low, high, fmt='%.2f'):
    changed, value = imgui.slider_float(label + '##' + key, float(branch.get(key, low)),
                                        low, high, fmt)
    if changed:
        branch[key] = value
    return changed


def slider_int(branch, key, label, low, high):
    changed, value = imgui.slider_int(label + '##' + key, int(branch.get(key, low)), low, high)
    if changed:
        branch[key] = value
    return changed


def checkbox(branch, key, label):
    changed, value = imgui.checkbox(label + '##' + key, bool(branch.get(key)))
    if changed:
        branch[key] = value
    return changed


def combo(branch, key, label, choices, captions=None):
    current = branch.get(key, choices[0] if choices else '')
    index = choices.index(current) if current in choices else 0
    changed, index = imgui.combo(label + '##' + key, index,
                                 [tr(c) for c in (captions or choices)])
    if changed:
        branch[key] = choices[index]
    return changed


def picker(label, current, entries, empty='(none)'):
    """A combo over {id, name} entries; returns the chosen id or '' for none."""
    identifiers = [''] + [entry['id'] for entry in entries]
    captions = [tr(empty)] + ['%s (%s)' % (entry.get('name', entry['id']), entry['id'])
                              for entry in entries]
    index = identifiers.index(current) if current in identifiers else 0
    changed, index = imgui.combo(label, index, captions)
    return (identifiers[index] if changed else current), changed


def dictionary_list(branch, key, label, fields, height=150):
    """Edit a list of small objects — locations, factions, rules, timeline entries."""
    values = list(branch.get(key) or [])
    changed = False
    imgui.push_id(key)
    imgui.separator_text(label)
    imgui.begin_child('list-' + key, (0, height), imgui.ChildFlags_.borders)
    removed = -1
    for index, item in enumerate(values):
        imgui.push_id(index)
        entry = dict(item)
        for field, caption, multiline_field in fields:
            if multiline_field:
                imgui.text(caption)
                edited, value = imgui.input_text_multiline('##' + field, str(entry.get(field, '')),
                                                           (-1, 48))
            else:
                edited, value = imgui.input_text(caption + '##' + field, str(entry.get(field, '')))
            if edited:
                entry[field] = value
                values[index] = entry
                changed = True
        if small_button('Remove'):
            removed = index
        imgui.separator()
        imgui.pop_id()
    imgui.end_child()
    if removed >= 0:
        values.pop(removed)
        changed = True
    if button('Add##add-' + key):
        values.append({field: '' for field, _, _ in fields})
        changed = True
    imgui.pop_id()
    if changed:
        branch[key] = values
    return changed


# --------------------------------------------------------------------------- tone

# Buttons all looked alike, so nothing said which one commits and which one destroys.
# The tones are blended into the theme's own button colour rather than hard-coded, so a
# light or classic theme chosen in Options still reads correctly.
# The neutral tone is desaturated on purpose: with the dark theme's own button already
# being blue, a blue "primary" is invisible next to it. Pushing the ordinary buttons towards
# grey is what makes the three meaningful colours read at a glance.
TONES = {
    'primary': (0.13, 0.55, 0.95),      # the action the panel exists for
    'confirm': (0.16, 0.62, 0.34),      # writes something down
    'danger': (0.80, 0.26, 0.26),       # moves something out of the way
    'quiet': (0.34, 0.35, 0.39),        # everything else, deliberately neutral
}
AMOUNTS = {'primary': 0.85, 'confirm': 0.85, 'danger': 0.85, 'quiet': 0.70}

_PRIMARY = ('send', 'say it', 'ask', 'capture', 'speak', 'test on', 'describe', 'install',
            'translate',
            'download', 'new ', 'open a discussion', 'import', 'export', 'run a diagnosis',
            'verify', 'check', 'activate', 'refresh')
_CONFIRM = ('save', 'keep', 'apply', 'add', 'create', 'restore', 'attach', 'duplicate')
_DANGER = ('trash', 'remove', 'discard', 'roll back', 'delete', 'release', 'unload',
           'cancel')


def tone_for(label):
    """Guess a tone from what the button says, so call sites stay readable."""
    text = str(label).split('##')[0].strip().lower()
    for word in _DANGER:
        if word in text:
            return 'danger'
    for word in _CONFIRM:
        if text.startswith(word):
            return 'confirm'
    for word in _PRIMARY:
        if text.startswith(word):
            return 'primary'
    return 'quiet'


def _lighter(target, factor):
    return tuple(min(1.0, channel * factor) for channel in target)


def _blend(base, target, amount):
    return imgui.ImVec4(base.x + (target[0] - base.x) * amount,
                        base.y + (target[1] - base.y) * amount,
                        base.z + (target[2] - base.z) * amount, base.w)


def _push(kind):
    target = TONES.get(kind)
    if target is None:
        return 0
    amount = AMOUNTS.get(kind, 0.8)
    native = raw()
    base = native.get_style().color_(native.Col_.button)
    native.push_style_color(native.Col_.button, _blend(base, target, amount))
    native.push_style_color(native.Col_.button_hovered,
                            _blend(base, _lighter(target, 1.35), amount))
    native.push_style_color(native.Col_.button_active,
                            _blend(base, _lighter(target, 0.75), amount))
    return 3


def button(label, kind=None, size=None):
    """A button that says what kind of thing it does.

    `kind` accepts a size passed positionally, because several call sites give one.
    """
    if kind is not None and not isinstance(kind, str):
        kind, size = None, kind
    pushed = _push(kind or tone_for(label))
    try:
        return imgui.button(label, size) if size else imgui.button(label)
    finally:
        if pushed:
            raw().pop_style_color(pushed)


def small_button(label, kind=None):
    pushed = _push(kind or tone_for(label))
    try:
        return imgui.small_button(label)
    finally:
        if pushed:
            raw().pop_style_color(pushed)
