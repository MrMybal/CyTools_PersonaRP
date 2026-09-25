"""Free discussion, in tabs.

One tab per thread, a + to open another and a cross to close one. Nothing is saved by hand:
a turn writes the thread, and the unsent draft follows when you switch tabs or close the
window. Closing a tab moves the discussion to data/assistant/.trash, so a tab closed by
mistake is not a discussion lost.
"""
from cytools_core import CyToolError
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


def discussion(app):
    raw().text_wrapped(tr('Talk freely, with no character and no scene. Each tab is its own '
                          'discussion and is written to disk at every turn. What you have '
                          'said here can then be handed to the proposal tab.'))

    imgui.begin_disabled(app.busy)
    _threads_bar(app)
    imgui.end_disabled()

    if app.thread is None:
        if not app.threads:
            if widgets.button('Open a discussion'):
                try:
                    outputs = app.call('new_assistant_thread', {})
                    app.refresh_threads()
                    app.select_thread(outputs['id'])
                except CyToolError as exc:
                    app.error = str(exc)
        return

    thread = app.thread
    imgui.begin_child('discussion-transcript', (0, 300), imgui.ChildFlags_.borders)
    turns = thread.get('turns') or []
    if not turns:
        raw().text_disabled(tr('Nothing said yet.'))
    for turn in turns:
        imgui.separator_text(tr('You') if turn.get('role') == 'user' else tr('Assistant'))
        raw().text_wrapped(str(turn.get('content', '')))
    if app.busy and app.purpose == 'assistant_chat':
        imgui.separator_text(tr('Assistant'))
        raw().text_disabled(tr('Writing...'))
    imgui.end_child()

    guide = getattr(app, 'discussion_image', None)
    if guide is None:
        guide = app.discussion_image = {'image': ''}
    widgets.text_field(guide, 'image',
                       tr('Attach a picture (full path, or a file in data/inputs)'))
    raw().text_disabled(tr('It is read by the vision model and what it shows is added to your '
                           'message as a visual reference for the character.'))

    imgui.text(tr('Your message — Enter sends, Ctrl+Enter adds a line'))
    entered, thread['draft'] = imgui.input_text_multiline(
        '##discussion-draft', thread.get('draft', ''), (-1, 80),
        raw().InputTextFlags_.enter_returns_true | raw().InputTextFlags_.ctrl_enter_for_new_line)
    send = entered and not raw().get_io().key_ctrl

    imgui.begin_disabled(app.busy)
    if widgets.button('Send##discussion'):
        send = True
    imgui.same_line()
    if widgets.button('Rename'):
        app.renaming = not getattr(app, 'renaming', False)
    imgui.same_line()
    if widgets.button('Open the discussion folder'):
        open_path(DATA / 'assistant')
    imgui.end_disabled()

    if getattr(app, 'renaming', False):
        widgets.text_field(thread, 'title', tr('Title of this discussion'))
        if widgets.button('Keep this title'):
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

    if imgui.collapsing_header(tr('Settings of this discussion')):
        installed = [entry for entry in app.models if entry.get('installed')]
        identifiers = [''] + [entry['id'] for entry in installed]
        captions = [tr('(an installed model)')] + [entry['name'] for entry in installed]
        current = thread.get('llm_model', '')
        index = identifiers.index(current) if current in identifiers else 0
        picked, index = imgui.combo(tr('Model'), index, captions)
        if picked:
            thread['llm_model'] = identifiers[index]
            app.save_thread_draft()
        if widgets.combo(thread, 'device', tr('Device'), ['', 'cuda', 'cpu'],
                         [tr('(automatic)'), tr('NVIDIA GPU'), tr('CPU')]):
            app.save_thread_draft()
        widgets.slider_float(thread, 'temperature', tr('Creativity'), 0.0, 2.0)
        widgets.slider_int(thread, 'response_length', tr('Reply length (tokens)'), 64, 4096)
        widgets.multiline(thread, 'system', tr('Standing instruction for this discussion'), 70)
        if widgets.button('Keep these settings'):
            app.save_thread_draft()
            app.notice = 'Discussion settings saved.'
