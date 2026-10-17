"""The Batches tab: tasks that speak a list of lines into a folder of takes.

Everything here goes through the speak_batch, speak_batch_file and list_batches operations,
the same ones the CLI and MCP use. A task can bring its own characters (bundles exported with
their recordings), is checked first (dry run: who speaks each line, with which voice), then
started — or queued behind the one already running. Its folder can be opened, and an
interrupted task resumed without paying again for the lines already written.
"""
import cyui
from ui_common import imgui, raw, tr

from personarp.paths import DATA, EXPORTS
from personarp.voice import batching

from . import widgets
from .state import open_path, shown
from .voice_panel import SHEET_TAB, language_combo

DEVICES = ['cuda', 'cpu']
SOURCES = ['From a file', 'Typed script']
STATUS_CAPTIONS = {'pending': 'Ready', 'ok': 'Done', 'error': 'Cannot be spoken'}
MODE_CAPTIONS = {'clone': 'stable voice', 'design': 'invented voice', 'custom': 'preset speaker'}
ORIGIN_CAPTIONS = {'task': 'task', 'library': 'library', 'voice': 'voice only'}
BATCH_PURPOSES = ('speak_batch', 'batch_check')
EXAMPLE_SCRIPT = ('# One line per reply: "Name: text", or "ID | Name: text" to give it its id.\n'
                  '# A line without a name continues the previous one.\n'
                  'SC01-01 | Maëlis: [ton: bas] Tu es en retard.\n'
                  'SC01-02 | Brannoc: Le col était pris par la neige.\n')


def form(app):
    """The fields of the tab, kept on the application so they survive a tab change."""
    state = getattr(app, 'batch_form', None)
    if state is None:
        state = app.batch_form = {
            'source': 0, 'file': '', 'text': EXAMPLE_SCRIPT, 'name': '', 'language': '',
            'device': 'cuda', 'auto': True, 'size': 8, 'seed': 42, 'dialog': None,
            'personas': [], 'use_library': True, 'persona_dialog': None,
            'preview': None, 'last': None, 'batches': None, 'folder': ''}
    return state


def request(state, **extra):
    """The operation and its parameters, exactly as the form shows them.

    Anything read from the disk — the list or the task's characters — goes through
    speak_batch_file; a typed script alone is sent inline to speak_batch.
    """
    values = {'name': state['name'].strip(), 'language': state['language'],
              'device': state['device'], 'seed': int(state['seed']),
              'batch_size': 0 if state['auto'] else int(state['size'])}
    if state['source'] == 0:
        values['file'] = state['file'].strip()
    else:
        values['text'] = state['text']
    operation = 'speak_batch'
    if state['source'] == 0 or state['personas']:
        operation = 'speak_batch_file'
        values['personas'] = list(state['personas'])
        values['use_library'] = bool(state['use_library'])
    values.update(extra)
    return operation, values


def launch(app, operation, parameters, purpose):
    """Start now, or queue behind the task that is running: tasks run one after the other."""
    if app.busy:
        app.pending.append((operation, parameters, purpose))
        app.notice = tr('Task queued: %d waiting.') % queued(app)
    else:
        app.submit(operation, parameters, purpose)


def queued(app):
    return sum(1 for _, _, purpose in app.pending if purpose in BATCH_PURPOSES)


def _refresh(app, state):
    try:
        outputs = app.call('list_batches', flush=False)
        state['batches'] = outputs.get('batches', [])
        state['folder'] = outputs.get('folder', '')
    except Exception as exc:                                    # noqa: BLE001 - shown to the user
        app.error = str(exc)
        state['batches'] = []


def _browse(state):
    dialog = state.get('dialog')
    if dialog is not None and dialog.ready():
        chosen = dialog.result()
        if chosen:
            state['file'] = chosen[0]
        state['dialog'] = None
    if widgets.icon_button(cyui.icon.open_file, 'Browse'):
        from imgui_bundle import portable_file_dialogs as pfd
        state['dialog'] = pfd.open_file(tr('Batch file'), str(DATA / 'inputs'),
                                        [tr('Batch'), '*.txt *.csv *.tsv *.json',
                                         tr('All files'), '*'])


def _help():
    if not cyui.begin_section(tr('Batch formats') + '###batch-formats', False):
        return
    raw().push_text_wrap_pos(0.0)
    for text in (
            'Script (.txt): one line per reply, "Name: text". A line without a name continues '
            'the previous reply; a line starting with # is a comment. Delivery marks such as '
            '[ton: ...] and [pause: 400ms] are kept.',
            'A line can carry its id: "SC01-05 | Maëlis: text". Its take is then named '
            'SC01-05.wav; a line without an id gets its number.',
            'CSV (; , or tab): a header row naming the columns — personnage/character, '
            'texte/text, and optionally id, voix/voice, langue/language, fichier/file. Without '
            'a header: character, text, language, file.',
            'JSON: a list of objects with the same fields, or {"lines": [...]}.',
            'A character is found by its identifier, its name, an alias, or a first or last '
            'name that only one character has. "voix" names a stable voice instead, or on top '
            'of the character. A line without a language uses the batch language, and the '
            'batch language empty speaks each character in its own.'):
        raw().bullet()
        cyui.text_dim(tr(text))
    raw().pop_text_wrap_pos()
    cyui.end_section()


def _settings(app, state):
    widgets.section('The lines')
    with widgets.properties('##batch-lines'):
        widgets.row('Source')
        _, state['source'] = cyui.segmented('##batch-source', [tr(s) for s in SOURCES],
                                            state['source'], -1)
        if state['source'] == 0:
            widgets.row('Batch file')
            raw().set_next_item_width(-(imgui.get_frame_height() + cyui.dp(4.0)) * 2
                                      - cyui.dp(4.0))
            _, state['file'] = raw().input_text('##batch-file', state['file'])
            imgui.same_line()
            _browse(state)
            imgui.same_line()
            if widgets.icon_button(cyui.icon.folder, 'Open data/inputs'):
                open_path(DATA / 'inputs')
    if state['source'] == 1:
        with cyui.scoped_font(cyui.mono_font()):
            _, state['text'] = raw().input_text_multiline('##batch-script', state['text'],
                                                          (-1, cyui.dp(150.0)))
    widgets.section('How they are spoken')
    with widgets.properties('##batch-settings'):
        widgets.row('Task name (optional)')
        _, state['name'] = raw().input_text('##batch-name', state['name'])
        state['language'], _ = language_combo('Language spoken##batch', state['language'],
                                              "(each character's own language)")
        index = DEVICES.index(state['device']) if state['device'] in DEVICES else 0
        widgets.row('Compute device')
        _, index = cyui.segmented('##batch-device', [tr('Graphics card (CUDA)'),
                                                     tr('Processor (slow)')], index, -1)
        state['device'] = DEVICES[index]
        widgets.checkbox(state, 'auto', 'Size the batches to the free graphics memory')
        if state['auto']:
            widgets.hint(tr('A first batch of %d measures what a line really costs on this '
                            'card; the next ones are sized from the memory left. A batch that '
                            'does not fit is halved and tried again.') % batching.PROBE_BATCH)
        else:
            widgets.slider_int(state, 'size', 'Lines at a time', 1, 64)
        widgets.integer(state, 'seed', 'Seed', 0, 42)


def _personas(state):
    """The characters the task brings with it, from bundles exported by PersonaRP."""
    widgets.section('Characters of the task')
    widgets.hint(tr(
        'Complete characters exported by PersonaRP (Library > Export and import, with the '
        'reference recordings): the sheet, its world and every stable voice, those of the other '
        'languages too. They are copied into the task folder, never into your library, and '
        'are looked up before it.'))
    dialog = state.get('persona_dialog')
    if dialog is not None and dialog.ready():
        for chosen in dialog.result() or []:
            if chosen not in state['personas']:
                state['personas'].append(chosen)
        state['persona_dialog'] = None
    for index, path in enumerate(list(state['personas'])):
        imgui.push_id('task-persona-%d' % index)
        removed = widgets.icon_button(cyui.icon.remove, 'Remove')
        imgui.same_line()
        raw().align_text_to_frame_padding()
        raw().text_unformatted(path)
        imgui.pop_id()
        if removed:
            state['personas'].pop(index)
            break
    if cyui.icon_text_button(cyui.icon.add, tr('Add character bundles'), 'ghost'):
        from imgui_bundle import portable_file_dialogs as pfd
        state['persona_dialog'] = pfd.open_file(
            tr('Character bundles'), str(EXPORTS),
            [tr('Character bundle'), '*.zip *.json', tr('All files'), '*'], pfd.opt.multiselect)
    imgui.same_line(0.0, cyui.dp(18.0))
    _, state['use_library'] = cyui.toggle_switch(tr('Also look in my library'),
                                                 state['use_library'])
    if not state['use_library'] and not state['personas']:
        cyui.callout('warning', tr('Without the library, only stable voices named in the list '
                                   'and the characters added here can speak.'))


def _preview(state):
    preview = state.get('preview')
    if not preview:
        return
    cyui.space(6.0)
    tone = 'warning' if preview['failed'] else 'success'
    cyui.begin_card('batch-check', tr('Check'), 0.0, tone)
    text = tr('%d line(s): %d ready, %d cannot be spoken.') % (
        preview['lines'], preview['ready'], preview['failed'])
    if preview.get('skipped'):
        text += ' ' + tr('%d already done.') % preview['skipped']
    raw().text_wrapped(text)
    if preview.get('personas'):
        cyui.text_dim(tr('Characters of the task: ') + ', '.join(
            item['name'] for item in preview['personas']))
    for problem in preview.get('problems', []):
        cyui.callout('warning', shown(problem))
    for position, group in enumerate(preview.get('groups', [])):
        if position:
            imgui.same_line()
        cyui.badge('%s — %s: %d' % (tr(MODE_CAPTIONS.get(group['mode'], group['mode'])),
                                    group['model'], group['lines']), 'info')
    cyui.space(4.0)
    flags = (raw().TableFlags_.borders_inner_h | raw().TableFlags_.row_bg
             | raw().TableFlags_.scroll_y | raw().TableFlags_.resizable)
    if raw().begin_table('batch-preview', 7, flags, (0, cyui.dp(240.0))):
        for caption in ('ID', 'Character', 'From', 'Voice', 'Language', 'Text', 'Status'):
            raw().table_setup_column(tr(caption))
        raw().table_setup_scroll_freeze(0, 1)
        raw().table_headers_row()
        p = cyui.palette()
        for line in preview.get('preview', []):
            raw().table_next_row()
            cells = (line.get('id') or str(line['index']),
                     line.get('speakerName') or line.get('character') or '',
                     tr(ORIGIN_CAPTIONS.get(line.get('speakerSource'), '')),
                     '%s %s' % (tr(MODE_CAPTIONS.get(line.get('mode'), '')),
                                line.get('voiceUsed', '')),
                     tr(line.get('languageUsed') or line.get('language') or ''),
                     line.get('text', '')[:120])
            for column, value in enumerate(cells):
                raw().table_set_column_index(column)
                raw().text_unformatted(value.strip())
            raw().table_set_column_index(6)
            if line.get('status') == 'error':
                cyui.text_coloured(p.error, tr('Cannot be spoken'))
                cyui.tooltip(shown(line.get('error', '')))
                raw().same_line()
                cyui.text_faint(shown(line.get('error', ''))[:80])
            else:
                cyui.text_coloured(p.success if line.get('status') == 'ok' else p.textDim,
                                   tr(STATUS_CAPTIONS.get(line.get('status'), '')))
                if line.get('note'):
                    raw().same_line()
                    cyui.text_faint(shown(line['note'])[:80])
        raw().end_table()
    cyui.end_card()


def _last(state):
    last = state.get('last')
    if not last:
        return
    cyui.space(6.0)
    tone = 'warning' if last.get('failed') else 'success'
    cyui.begin_card('batch-last', tr('Last task'), 0.0, tone)
    raw().text_wrapped(tr('%s: %d of %d line(s) written, %d failed, %d already done.') % (
        last.get('batch', ''), last.get('done', 0), last.get('lines', 0), last.get('failed', 0),
        last.get('skipped', 0)))
    for group in last.get('groups', []):
        peak = group.get('vramPeakBytes')
        raw().bullet()
        cyui.text_dim(tr('%s: %d passage(s), %d at a time (first try %d, %d memory retry), '
                         '%.1f s%s') % (
            tr(MODE_CAPTIONS.get(group.get('mode'), group.get('mode') or '')),
            group.get('passages') or 0, group.get('batchSize') or 0,
            group.get('firstBatchSize') or 0, group.get('memoryRetries') or 0,
            group.get('generationSeconds') or 0.0,
            (tr(', VRAM peak %.1f GB') % (peak / 1024 ** 3)) if peak else ''))
    for problem in last.get('problems', []):
        cyui.callout('warning', shown(problem))
    for error in last.get('errors', [])[:8]:
        cyui.text_faint(tr('Line %s: %s') % (error.get('id') or error['index'],
                                             shown(error['error'])))
    if cyui.icon_text_button(cyui.icon.folder, tr('Open the folder') + '##last-batch', 'outline'):
        open_path(last.get('folder', ''))
    cyui.end_card()


def _listing(app, state):
    if widgets.icon_button(cyui.icon.refresh, 'Refresh'):
        state['batches'] = None
    imgui.same_line()
    if widgets.icon_button(cyui.icon.folder, 'Open the batches folder'):
        open_path(state.get('folder') or DATA / 'batches')
    waiting = queued(app)
    if waiting:
        imgui.same_line()
        cyui.badge(tr('%d task(s) waiting in the queue.') % waiting, 'info')
        imgui.same_line()
        if widgets.small_button('Empty the queue'):
            app.pending = [item for item in app.pending if item[2] not in BATCH_PURPOSES]
    if state['batches'] is None:
        _refresh(app, state)
    if not state['batches']:
        widgets.empty('No task yet', 'Prepare one in New task.', cyui.icon.list)
        return
    flags = raw().TableFlags_.row_bg | raw().TableFlags_.borders_inner_h
    if not raw().begin_table('##batches', 4, flags):
        return
    raw().table_setup_column(tr('Lines'), raw().TableColumnFlags_.width_fixed, cyui.dp(110.0))
    raw().table_setup_column(tr('Task'), raw().TableColumnFlags_.width_stretch)
    raw().table_setup_column(tr('Created'), raw().TableColumnFlags_.width_fixed, cyui.dp(160.0))
    raw().table_setup_column('##actions', raw().TableColumnFlags_.width_fixed,
                             imgui.get_frame_height() * 3 + cyui.dp(16.0))
    raw().table_headers_row()
    for item in state['batches'][:50]:
        imgui.push_id('batch-' + item['id'])
        raw().table_next_row()
        raw().table_set_column_index(0)
        lines = max(1, item.get('lines', 0))
        cyui.progress_bar(item.get('done', 0) / lines, (-1.0, 0.0),
                          '%d/%d' % (item.get('done', 0), item.get('lines', 0)),
                          'success' if item.get('complete') else 'warning')
        raw().table_set_column_index(1)
        raw().align_text_to_frame_padding()
        raw().text_unformatted(item.get('name', item['id']))
        if item.get('failed'):
            imgui.same_line()
            cyui.badge(tr('%d failed') % item['failed'], 'error')
        raw().table_set_column_index(2)
        raw().align_text_to_frame_padding()
        cyui.text_faint(item.get('created', ''))
        raw().table_set_column_index(3)
        if widgets.icon_button(cyui.icon.folder, 'Open the folder'):
            open_path(item['folder'])
        if not item.get('complete'):
            imgui.same_line()
            if widgets.icon_button(cyui.icon.view, 'Check what is left'):
                launch(app, 'speak_batch', {'resume': item['id'], 'dry_run': True,
                                            'device': state['device']}, 'batch_check')
            imgui.same_line()
            if widgets.icon_button(cyui.icon.play, 'Resume'):
                launch(app, 'speak_batch', {
                    'resume': item['id'], 'device': state['device'], 'seed': int(state['seed']),
                    'batch_size': 0 if state['auto'] else int(state['size'])}, 'speak_batch')
        imgui.pop_id()
    raw().end_table()


def _new_task(app, state):
    _help()
    _settings(app, state)
    _personas(state)
    cyui.space(6.0)
    ready = bool(state['file'].strip()) if state['source'] == 0 else bool(state['text'].strip())
    imgui.begin_disabled(not ready)
    if cyui.icon_text_button(cyui.icon.view, tr('Check the task'), 'outline'):
        launch(app, *request(state, dry_run=True), 'batch_check')
    imgui.same_line()
    if cyui.icon_text_button(cyui.icon.play,
                             tr('Queue the task' if app.busy else 'Start the task'), 'primary'):
        launch(app, *request(state), 'speak_batch')
    imgui.end_disabled()
    if not ready:
        imgui.same_line()
        raw().align_text_to_frame_padding()
        cyui.text_faint(tr('Give a batch file or type a script first.'))
    _preview(state)
    _last(state)


def batch_tab(app):
    state = form(app)
    widgets.hint(tr(
        'Speak a whole list of lines in one go. The lines are generated many at a time in one '
        'copy of the voice model, as many as the free graphics memory holds, so a large GPU '
        'rented by the hour is used to the full. Each task gets its own folder in '
        'data/batches: its characters, the list as given, one WAV per line named after its '
        'id in voix/, and resultats.csv. Tasks started while another runs wait their turn.'))
    cyui.space(4.0)
    page = widgets.page_tabs('batch-pages', ['New task', 'Tasks'], SHEET_TAB)
    imgui.begin_child('batch-body', (0, 0), 0)
    if page == 'New task':
        _new_task(app, state)
    else:
        _listing(app, state)
    cyui.space(12.0)
    imgui.end_child()
