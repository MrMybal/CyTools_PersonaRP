"""Small editing widgets shared by the panels, drawn with CyUI (app/cyui.py).

The character sheet is deep, so these helpers edit a branch of it in place and report
whether anything changed — which is what drives the "unsaved changes" marker.

Inside `with properties('##id'):` the field helpers become rows of a property table — the
label on the left, dimmed, the control on the right at full width — which is how CyUI lays
out settings and inspectors. Outside one, they keep ImGui's own layout.
"""
import contextlib

from imgui_bundle import ImVec2

import cyui
from ui_common import imgui, raw, tr

_tables = []        # one entry per open properties table: whether it really opened


def _in_properties():
    return bool(_tables) and _tables[-1]


@contextlib.contextmanager
def properties(identifier, label_width=0.0):
    """Label / value rows for the field helpers below. The label column stays narrow on a
    wide window: the values are what gets typed in."""
    if label_width <= 0.0:
        room = raw().get_content_region_avail().x / max(cyui.dpi(), 0.01)
        label_width = max(120.0, min(250.0, room * 0.38))
    opened = cyui.begin_properties(identifier, label_width)
    _tables.append(opened)
    try:
        yield opened
    finally:
        _tables.pop()
        if opened:
            cyui.end_properties()


def _row(label, help_text=''):
    """In a properties table, the label cell; returns the ID-only label for the control."""
    cyui.property(tr(label.split('##')[0]), tr(help_text) if help_text else '')
    return '##' + label


# --------------------------------------------------------------------------- text

def hint(text):
    """Secondary information under a control: faint and wrapped, never past the window."""
    if not text:
        return
    if _in_properties():
        raw().table_next_row()
        raw().table_set_column_index(1)
    raw().push_text_wrap_pos(0.0)
    cyui.text_faint(text)
    raw().pop_text_wrap_pos()


def section(title):
    """The title of a group of fields inside a page."""
    cyui.space(4.0)
    cyui.section_title(tr(title))
    cyui.divider(2.0)


def warning(text):
    cyui.callout('warning', text)


def empty(title, message='', glyph=''):
    """A panel with nothing in it says why, and what to do."""
    cyui.empty_state(tr(title), tr(message) if message else '', glyph)


# ------------------------------------------------------------------------- fields

def text_field(persona_branch, key, label, width=0.0):
    if _in_properties():
        changed, value = raw().input_text(_row(label) + key, str(persona_branch.get(key, '')))
    else:
        changed, value = imgui.input_text(label + '##' + key, str(persona_branch.get(key, '')))
    if changed:
        persona_branch[key] = value
    return changed


def multiline(persona_branch, key, label, height=64):
    if _in_properties():
        _row(label)
        changed, value = raw().input_text_multiline('##' + key, str(persona_branch.get(key, '')),
                                                    (-1, cyui.dp(height)))
    else:
        cyui.text_dim(tr(label))
        changed, value = imgui.input_text_multiline('##' + key, str(persona_branch.get(key, '')),
                                                    (-1, cyui.dp(height)))
    if changed:
        persona_branch[key] = value
    return changed


def string_list(persona_branch, key, label, hint_text=''):
    """A list of short entries, edited one line per entry."""
    values = list(persona_branch.get(key) or [])
    changed = False
    imgui.push_id(key)
    if _in_properties():
        _row(label, hint_text)
    else:
        cyui.text_dim(tr(label))
        if hint_text:
            cyui.help_marker(tr(hint_text))
    removed = -1
    for index, entry in enumerate(values):
        imgui.push_id(index)
        raw().set_next_item_width(-cyui.imgui.get_frame_height() - cyui.dp(8.0))
        edited, value = raw().input_text('##entry', str(entry))
        if edited:
            values[index] = value
            changed = True
        imgui.same_line()
        if cyui.icon_button(cyui.icon.remove, tr('Remove this entry')):
            removed = index
        imgui.pop_id()
    if removed >= 0:
        values.pop(removed)
        changed = True
    if cyui.icon_text_button(cyui.icon.add, tr('Add'), 'ghost'):
        values.append('')
        changed = True
    imgui.pop_id()
    if changed:
        persona_branch[key] = values
    return changed


def slider_float(branch, key, label, low, high, fmt='%.2f'):
    current = float(branch.get(key, low))
    if _in_properties():
        changed, value = raw().slider_float(_row(label) + key, current, low, high, fmt)
    else:
        changed, value = imgui.slider_float(label + '##' + key, current, low, high, fmt)
    if changed:
        branch[key] = value
    return changed


def slider_int(branch, key, label, low, high):
    current = int(branch.get(key, low))
    if _in_properties():
        changed, value = raw().slider_int(_row(label) + key, current, low, high)
    else:
        changed, value = imgui.slider_int(label + '##' + key, current, low, high)
    if changed:
        branch[key] = value
    return changed


def checkbox(branch, key, label):
    """An on/off setting: a CyUI switch."""
    if _in_properties():
        changed, value = cyui.toggle_switch(_row(label) + key, bool(branch.get(key)))
    else:
        changed, value = cyui.toggle_switch(tr(label.split('##')[0]) + '##' + key, bool(branch.get(key)))
    if changed:
        branch[key] = value
    return changed


def combo(branch, key, label, choices, captions=None):
    current = branch.get(key, choices[0] if choices else '')
    index = choices.index(current) if current in choices else 0
    items = [tr(c) for c in (captions or choices)]
    if _in_properties():
        changed, index = raw().combo(_row(label) + key, index, items)
    else:
        changed, index = imgui.combo(label + '##' + key, index, items)
    if changed:
        branch[key] = choices[index]
    return changed


def row(label, help_text=''):
    """Start a row for a control drawn by the caller; returns the label to give it."""
    if _in_properties():
        return _row(label, help_text)
    return tr(label.split('##')[0]) + '##' + label


def choice(label, index, captions, help_text=''):
    """A combo over captions already translated; returns (changed, index)."""
    return raw().combo(row(label, help_text), index, captions)


def integer(branch, key, label, low=None, default=0, help_text=''):
    """A whole number typed in, clamped at `low`."""
    current = int(branch.get(key, default))
    changed, value = raw().input_int(row(label, help_text) + key, current)
    if changed and value != current:
        branch[key] = value if low is None else max(low, value)
        return True
    return False


def picker(label, current, entries, empty='(none)'):
    """A combo over {id, name} entries; returns the chosen id or '' for none."""
    identifiers = [''] + [entry['id'] for entry in entries]
    captions = [tr(empty)] + ['%s (%s)' % (entry.get('name', entry['id']), entry['id'])
                              for entry in entries]
    index = identifiers.index(current) if current in identifiers else 0
    if _in_properties():
        changed, index = raw().combo(_row(label), index, captions)
    else:
        changed, index = imgui.combo(label, index, captions)
    return (identifiers[index] if changed else current), changed


def dictionary_list(branch, key, label, fields, height=150):
    """Edit a list of small objects — locations, factions, rules, timeline entries."""
    values = list(branch.get(key) or [])
    changed = False
    imgui.push_id(key)
    section(label)
    removed = -1
    for index, item in enumerate(values):
        imgui.push_id(index)
        entry = dict(item)
        title = str(entry.get(fields[0][0], '')).strip() or tr('(untitled)')
        cyui.begin_card('entry', '')
        raw().align_text_to_frame_padding()
        cyui.text_dim(title)
        imgui.same_line()
        cyui.align_right(imgui.get_frame_height())
        if cyui.icon_button(cyui.icon.trash, tr('Remove this entry')):
            removed = index
        with properties('##fields') as opened:
            for field, caption, multiline_field in (fields if opened else []):
                cyui.property(tr(caption))
                if multiline_field:
                    edited, value = raw().input_text_multiline('##' + field, str(entry.get(field, '')),
                                                               (-1, cyui.dp(48)))
                else:
                    edited, value = raw().input_text('##' + field, str(entry.get(field, '')))
                if edited:
                    entry[field] = value
                    values[index] = entry
                    changed = True
        cyui.end_card()
        imgui.pop_id()
    if removed >= 0:
        values.pop(removed)
        changed = True
    if cyui.icon_text_button(cyui.icon.add, tr('Add'), 'ghost'):
        values.append({field: '' for field, _, _ in fields})
        changed = True
    imgui.pop_id()
    if changed:
        branch[key] = values
    return changed


# ---------------------------------------------------------------------------- tabs

_current_tabs = {}


def page_tabs(identifier, captions, forced=''):
    """The sub-pages of a page, as a row of flat tabs: the current one in full text and
    underlined in the accent colour, the others dimmed. Wraps when the row is too narrow.
    Returns the caption (English, untranslated) of the current sub-page."""
    current = forced if forced in captions else _current_tabs.get(identifier, captions[0])
    if current not in captions:
        current = captions[0]
    p = cyui.palette()
    style = raw().get_style()
    draw = raw().get_window_draw_list()
    right = raw().get_cursor_screen_pos().x + raw().get_content_region_avail().x
    height = raw().get_frame_height()
    for index, caption in enumerate(captions):
        text = tr(caption)
        width = raw().calc_text_size(text).x + style.frame_padding.x * 2.0
        if index:
            raw().same_line(0.0, cyui.dp(2.0))
            if raw().get_cursor_screen_pos().x + width > right:
                raw().new_line()
        origin = raw().get_cursor_screen_pos()
        if raw().invisible_button('##%s-%s' % (identifier, caption), ImVec2(width, height)):
            current = caption
        active = caption == current
        hovered = raw().is_item_hovered()
        end = ImVec2(origin.x + width, origin.y + height)
        if hovered and not active:
            draw.add_rect_filled(origin, end, p.bg3, style.frame_rounding)
        draw.add_text(ImVec2(origin.x + style.frame_padding.x, origin.y + style.frame_padding.y),
                      p.text if active or hovered else p.textDim, text)
        if active:
            draw.add_line(ImVec2(origin.x + cyui.dp(3.0), end.y - cyui.dp(1.0)),
                          ImVec2(end.x - cyui.dp(3.0), end.y - cyui.dp(1.0)), p.accent,
                          cyui.dp(2.0))
    origin = raw().get_cursor_screen_pos()
    draw.add_line(origin, ImVec2(right, origin.y), p.line)
    cyui.space(6.0)
    _current_tabs[identifier] = current
    return current


# -------------------------------------------------------------------------- buttons

# The role of a button, guessed from what it says so call sites stay readable. CyUI keeps
# one accent for the action a panel exists for; what writes is outlined, what removes is
# red, the rest is a plain button.
_PRIMARY = ('send', 'say it', 'ask', 'capture', 'speak', 'test on', 'describe', 'install',
            'translate', 'download', 'run a diagnosis')
_CONFIRM = ('save', 'keep', 'apply', 'add', 'create', 'restore', 'attach', 'duplicate', 'import',
            'export', 'new ', 'verify', 'check', 'activate', 'refresh', 'open a discussion')
_DANGER = ('trash', 'remove', 'discard', 'roll back', 'delete', 'release', 'unload', 'cancel')
VARIANT = {'primary': 'primary', 'confirm': 'outline', 'danger': 'danger', 'quiet': 'secondary'}


def tone_for(label):
    """Guess a role from what the button says."""
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


def _variant(label, kind):
    kind = kind or tone_for(label)
    return VARIANT.get(kind, kind if kind in cyui.VARIANTS else 'secondary')


def button(label, kind=None, size=None):
    """A button that says what kind of thing it does.

    `kind` accepts a size passed positionally, because several call sites give one.
    """
    if kind is not None and not isinstance(kind, str):
        kind, size = None, kind
    from ui_common import label as translated
    return cyui.button(translated(label), _variant(label, kind), tuple(size) if size else (0.0, 0.0))


def small_button(label, kind=None):
    from ui_common import label as translated
    return cyui.button(translated(label), _variant(label, kind), small=True)


def icon_button(glyph, tip, active=False):
    """A toolbar action: an icon, and a tooltip that names it."""
    return cyui.icon_button(glyph, tr(tip), active)
