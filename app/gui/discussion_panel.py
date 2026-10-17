"""Free discussion, in tabs.

One tab per thread, a + to open another and a cross to close one. Nothing is saved by hand:
a turn writes the thread, and the unsent draft follows when you switch tabs or close the
window. Closing a tab moves the discussion to data/assistant/.trash, so a tab closed by
mistake is not a discussion lost.
"""
from cytools_core import CyToolError
import cyui
from ui_common import imgui, raw, tr

from personarp.paths import DATA

from . import widgets
from .state import open_path


def _threads_bar(app):
    """The tab bar itself. Returns True when the selection changed."""
    changed = False
    if not imgui.begin_tab_bar('discussions', raw().TabBarFlags_.auto_select_new_tabs
                               | raw().TabBarFlags_.reorderable):
        return changed
    closing = ''
    for entry in app.threads:
        label = '%s##%s' % ((entry['title'] or 'Discussion')[:34], entry['id'])
        opened, keep = imgui.begin_tab_item(label, True)
        if not keep:
            closing = entry['id']
        if opened:
            if app.thread_id != entry['id']:
                app.select_thread(entry['id'])
                changed = True
            imgui.end_tab_item()
    if imgui.tab_item_button('+', raw().TabItemFlags_.trailing | raw().TabItemFlags_.no_tooltip):
        try:
            app.save_thread_draft()
            outputs = app.call('new_assistant_thread', {})
            app.refresh_threads()
            app.select_thread(outputs['id'])
            changed = True
        except CyToolError as exc:
            app.error = str(exc)
    imgui.end_tab_bar()

    if closing:
        try:
            app.call('remove_assistant_thread', {'thread_id': closing})
            app.notice = 'Discussion moved to data/assistant/.trash — nothing was deleted.'
            if app.thread_id == closing:
                app.thread_id = ''
                app.thread = None
            app.refresh_threads()
            changed = True
        except CyToolError as exc:
            app.error = str(exc)
    return changed


def _transcript(thread, app, height):
    p = cyui.palette()
    with cyui.scoped_color(raw().Col_.child_bg, p.bg0):
        imgui.begin_child('discussion-transcript', (0, height), imgui.ChildFlags_.borders
                          | imgui.ChildFlags_.always_use_window_padding)
    turns = thread.get('turns') or []
    if not turns and not app.busy:
        widgets.empty('Nothing said yet', 'Write below: an idea, a question, a draft to discuss.',
                      cyui.icon.lightbulb)
    for turn in turns:
        mine = turn.get('role') == 'user'
        cyui.overline((tr('You') if mine else tr('Assistant')).upper(),
                      p.textDim if mine else 0)
        raw().push_text_wrap_pos(0.0)
        raw().text_unformatted(str(turn.get('content', '')))
        raw().pop_text_wrap_pos()
        cyui.space(8.0)
    if app.busy and app.purpose == 'assistant_chat':
        cyui.overline(tr('Assistant').upper())
        cyui.spinner('##assistant-writing', 7.0)
        imgui.same_line()
        cyui.text_faint(tr('Writing...'))
        raw().set_scroll_here_y(1.0)
    imgui.end_child()


def discussion(app):
    widgets.hint(tr('Talk freely, with no character and no scene. Each tab is its own '
                    'discussion and is written to disk at every turn. What you have said here '
                    'can then be handed to the proposal tab.'))

    imgui.begin_disabled(app.busy)
    _threads_bar(app)
    imgui.end_disabled()

    if app.thread is None:
        if not app.threads:
            if cyui.icon_text_button(cyui.icon.add, tr('Open a discussion'), 'primary'):
                try:
                    outputs = app.call('new_assistant_thread', {})
                    app.refresh_threads()
                    app.select_thread(outputs['id'])
                except CyToolError as exc:
                    app.error = str(exc)
            widgets.empty('No discussion yet', 'Open one to talk an idea through.',
                          cyui.icon.lightbulb)
        return

    thread = app.thread
    row = raw().get_frame_height_with_spacing()
    composer = cyui.dp(84.0) + row * 2 + cyui.dp(28.0) \
        + (row * 2 if getattr(app, 'renaming', False) else 0)
    _transcript(thread, app, max(cyui.dp(160.0), raw().get_content_region_avail().y - composer))

    guide = getattr(app, 'discussion_image', None)
    if guide is None:
        guide = app.discussion_image = {'image': ''}
    cyui.space(4.0)
    cyui.text_faint(tr('Your message — Enter sends, Ctrl+Enter adds a line'))
    entered, thread['draft'] = raw().input_text_multiline(
        '##discussion-draft', thread.get('draft', ''), (-1, cyui.dp(84.0)),
        raw().InputTextFlags_.enter_returns_true | raw().InputTextFlags_.ctrl_enter_for_new_line)
    send = entered and not raw().get_io().key_ctrl

    imgui.begin_disabled(app.busy)
    if cyui.icon_text_button(cyui.icon.send, tr('Send') + '##discussion', 'primary'):
        send = True
    imgui.same_line()
    raw().set_next_item_width(cyui.dp(340.0))
    _, guide['image'] = raw().input_text_with_hint(
        '##discussion-image', tr('Attach a picture (full path, or a file in data/inputs)'),
        guide['image'])
    cyui.tooltip(tr('It is read by the vision model and what it shows is added to your message '
                    'as a visual reference for the character.'))
    imgui.same_line()
    if widgets.icon_button(cyui.icon.rename, 'Rename', getattr(app, 'renaming', False)):
        app.renaming = not getattr(app, 'renaming', False)
    imgui.same_line()
    if widgets.icon_button(cyui.icon.folder, 'Open the discussion folder'):
        open_path(DATA / 'assistant')
    imgui.same_line()
    if widgets.icon_button(cyui.icon.settings, 'Settings of this discussion',
                           getattr(app, 'discussion_settings', False)):
        app.discussion_settings = True
    imgui.end_disabled()

    if getattr(app, 'renaming', False):
        with widgets.properties('##rename'):
            widgets.text_field(thread, 'title', 'Title of this discussion')
        if cyui.icon_text_button(cyui.icon.check, tr('Keep this title'), 'outline'):
            app.save_thread_draft()
            app.refresh_threads()
            app.renaming = False

    if send and str(thread.get('draft', '')).strip() and not app.busy:
        text = thread['draft']
        thread['draft'] = ''
        app.submit('assistant_chat', {'thread_id': thread['id'], 'text': text,
                                      'image': guide['image'],
                                      'keep_loaded': True}, 'assistant_chat')
        guide['image'] = ''
        thread.setdefault('turns', []).append({'role': 'user', 'content': text})

    _settings(app, thread)


def _settings(app, thread):
    """The model and the standing instruction of this discussion, in a dialog."""
    shown, app.discussion_settings = cyui.begin_modal(
        tr('Settings of this discussion') + '##discussion-settings',
        getattr(app, 'discussion_settings', False), 560.0)
    if not shown:
        return
    with widgets.properties('##discussion-settings'):
        installed = [entry for entry in app.models if entry.get('installed')]
        identifiers = [''] + [entry['id'] for entry in installed]
        captions = [tr('(an installed model)')] + [entry['name'] for entry in installed]
        current = thread.get('llm_model', '')
        index = identifiers.index(current) if current in identifiers else 0
        picked, index = widgets.choice('Model', index, captions)
        if picked:
            thread['llm_model'] = identifiers[index]
        widgets.combo(thread, 'device', 'Device', ['', 'cuda', 'cpu'],
                      [tr('(automatic)'), tr('NVIDIA GPU'), tr('CPU')])
        widgets.slider_float(thread, 'temperature', 'Creativity', 0.0, 2.0)
        widgets.slider_int(thread, 'response_length', 'Reply length (tokens)', 64, 4096)
        widgets.multiline(thread, 'system', 'Standing instruction for this discussion', 70)
    answer = cyui.modal_buttons(tr('Keep these settings'), tr('Close'))
    if answer == 1:
        app.save_thread_draft()
        app.notice = 'Discussion settings saved.'
    if answer:
        app.discussion_settings = False
    cyui.end_modal()
