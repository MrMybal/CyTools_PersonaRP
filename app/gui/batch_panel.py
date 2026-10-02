"""The Batches tab: tasks that speak a list of lines into a folder of takes.

Everything here goes through the speak_batch, speak_batch_file and list_batches operations,
the same ones the CLI and MCP use. A task can bring its own characters (bundles exported with
their recordings), is checked first (dry run: who speaks each line, with which voice), then
started — or queued behind the one already running. Its folder can be opened, and an
interrupted task resumed without paying again for the lines already written.
"""
from ui_common import imgui, raw, tr

from personarp.paths import DATA, EXPORTS
from personarp.voice import batching

from . import widgets
from .state import open_path, shown
from .voice_panel import language_combo

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
    if widgets.button('Browse##batch-file'):
        from imgui_bundle import portable_file_dialogs as pfd
        state['dialog'] = pfd.open_file(tr('Batch file'), str(DATA / 'inputs'),
                                        [tr('Batch'), '*.txt *.csv *.tsv *.json',
                                         tr('All files'), '*'])


def _help():
    if imgui.collapsing_header('Batch formats'):
        raw().text_wrapped(tr(
            'Script (.txt): one line per reply, "Name: text". A line without a name continues '
            'the previous reply; a line starting with # is a comment. Delivery marks such as '
            '[ton: ...] and [pause: 400ms] are kept.'))
        raw().text_wrapped(tr(
            'A line can carry its id: "SC01-05 | Maëlis: text". Its take is then named '
            'SC01-05.wav; a line without an id gets its number.'))
        raw().text_wrapped(tr(
            'CSV (; , or tab): a header row naming the columns — personnage/character, '
            'texte/text, and optionally id, voix/voice, langue/language, fichier/file. Without '
            'a header: character, text, language, file.'))
        raw().text_wrapped(tr(
            'JSON: a list of objects with the same fields, or {"lines": [...]}.'))
        raw().text_wrapped(tr(
            'A character is found by its identifier, its name, an alias, or a first or last '
            'name that only one character has. "voix" names a stable voice instead, or on top '
            'of the character. A line without a language uses the batch language, and the '
            'batch language empty speaks each character in its own.'))


def _settings(app, state):
    _, state['source'] = imgui.combo('Source##batch', state['source'], [tr(s) for s in SOURCES])
    if state['source'] == 0:
        _, state['file'] = imgui.input_text('Batch file', state['file'])
        imgui.same_line()
        _browse(state)
        imgui.same_line()
        if widgets.button('Open data/inputs##batch'):
            open_path(DATA / 'inputs')
    else:
        _, state['text'] = imgui.input_text_multiline('##batch-script', state['text'], (-1, 150))
    _, state['name'] = imgui.input_text('Task name (optional)', state['name'])
    state['language'], _ = language_combo(tr('Language spoken') + '##batch', state['language'],
                                          "(each character's own language)")
    index = DEVICES.index(state['device']) if state['device'] in DEVICES else 0
    _, index = imgui.combo('Compute device##batch', index, [tr('Graphics card (CUDA)'),
                                                            tr('Processor (slow)')])
    state['device'] = DEVICES[index]
    _, state['auto'] = imgui.checkbox('Size the batches to the free graphics memory',
                                      state['auto'])
    if state['auto']:
        raw().text_disabled(tr('A first batch of %d measures what a line really costs on this '
                               'card; the next ones are sized from the memory left. A batch that '
                               'does not fit is halved and tried again.') % batching.PROBE_BATCH)
    else:
        _, state['size'] = imgui.slider_int('Lines at a time', int(state['size']), 1, 64)
    _, state['seed'] = imgui.input_int('Seed##batch', int(state['seed']))
    state['seed'] = max(0, state['seed'])


def _personas(state):
    """The characters the task brings with it, from bundles exported by PersonaRP."""
    imgui.separator_text(tr('Characters of the task'))
    raw().text_wrapped(tr(
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
        removed = widgets.small_button('Remove')
        imgui.same_line()
        raw().text_unformatted(path)
        imgui.pop_id()
        if removed:
            state['personas'].pop(index)
            break
    if widgets.button('Add character bundles'):
        from imgui_bundle import portable_file_dialogs as pfd
        state['persona_dialog'] = pfd.open_file(
            tr('Character bundles'), str(EXPORTS),
            [tr('Character bundle'), '*.zip *.json', tr('All files'), '*'], pfd.opt.multiselect)
    imgui.same_line()
    _, state['use_library'] = imgui.checkbox('Also look in my library', state['use_library'])
    if not state['use_library'] and not state['personas']:
        raw().text_disabled(tr('Without the library, only stable voices named in the list and '
                               'the characters added here can speak.'))


def _preview(state):
    preview = state.get('preview')
    if not preview:
        return
    imgui.separator_text(tr('Check'))
    text = tr('%d line(s): %d ready, %d cannot be spoken.') % (
        preview['lines'], preview['ready'], preview['failed'])
    if preview.get('skipped'):
        text += ' ' + tr('%d already done.') % preview['skipped']
    raw().text_wrapped(text)
    if preview.get('personas'):
        raw().text_wrapped(tr('Characters of the task: ') + ', '.join(
            item['name'] for item in preview['personas']))
    for problem in preview.get('problems', []):
        imgui.text_colored(imgui.ImVec4(1.0, 0.75, 0.35, 1.0), shown(problem))
    for group in preview.get('groups', []):
        raw().bullet_text('%s — %s: %d' % (tr(MODE_CAPTIONS.get(group['mode'], group['mode'])),
                                           group['model'], group['lines']))
    flags = (raw().TableFlags_.borders | raw().TableFlags_.row_bg | raw().TableFlags_.scroll_y
             | raw().TableFlags_.resizable)
    if raw().begin_table('batch-preview', 7, flags, (0, 220)):
        for caption in ('ID', 'Character', 'From', 'Voice', 'Language', 'Text', 'Status'):
            raw().table_setup_column(tr(caption))
        raw().table_setup_scroll_freeze(0, 1)
        raw().table_headers_row()
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
                imgui.text_colored(imgui.ImVec4(1.0, 0.55, 0.45, 1.0), tr('Cannot be spoken'))
                if raw().is_item_hovered():
                    raw().set_tooltip(shown(line.get('error', '')))
                raw().same_line()
                raw().text_disabled(shown(line.get('error', ''))[:80])
            else:
                raw().text_unformatted(tr(STATUS_CAPTIONS.get(line.get('status'), '')))
                if line.get('note'):
                    raw().same_line()
                    raw().text_disabled(shown(line['note'])[:80])
        raw().end_table()


def _last(state):
    last = state.get('last')
    if not last:
        return
    imgui.separator_text(tr('Last task'))
    raw().text_wrapped(tr('%s: %d of %d line(s) written, %d failed, %d already done.') % (
        last.get('batch', ''), last.get('done', 0), last.get('lines', 0), last.get('failed', 0),
        last.get('skipped', 0)))
    for group in last.get('groups', []):
        peak = group.get('vramPeakBytes')
        raw().bullet_text(tr('%s: %d passage(s), %d at a time (first try %d, %d memory retry), '
                             '%.1f s%s') % (
            tr(MODE_CAPTIONS.get(group.get('mode'), group.get('mode') or '')),
            group.get('passages') or 0, group.get('batchSize') or 0,
            group.get('firstBatchSize') or 0, group.get('memoryRetries') or 0,
            group.get('generationSeconds') or 0.0,
            (tr(', VRAM peak %.1f GB') % (peak / 1024 ** 3)) if peak else ''))
    for problem in last.get('problems', []):
        imgui.text_colored(imgui.ImVec4(1.0, 0.75, 0.35, 1.0), shown(problem))
    for error in last.get('errors', [])[:8]:
        raw().text_disabled(tr('Line %s: %s') % (error.get('id') or error['index'],
                                                  shown(error['error'])))
    if widgets.button('Open the folder##last-batch'):
        open_path(last.get('folder', ''))


def _listing(app, state):
    imgui.separator_text(tr('Tasks'))
    if widgets.button('Refresh##batches'):
        state['batches'] = None
    imgui.same_line()
    if widgets.button('Open the batches folder'):
        open_path(state.get('folder') or DATA / 'batches')
    waiting = queued(app)
    if waiting:
        imgui.same_line()
        raw().text_disabled(tr('%d task(s) waiting in the queue.') % waiting)
        imgui.same_line()
        if widgets.small_button('Empty the queue'):
            app.pending = [item for item in app.pending if item[2] not in BATCH_PURPOSES]
    if state['batches'] is None:
        _refresh(app, state)
    if not state['batches']:
        raw().text_disabled(tr('No task yet.'))
        return
    for item in state['batches'][:50]:
        imgui.push_id('batch-' + item['id'])
        colour = (imgui.ImVec4(0.45, 0.85, 0.5, 1.0) if item.get('complete')
                  else imgui.ImVec4(1.0, 0.75, 0.35, 1.0))
        imgui.text_colored(colour, '%d/%d' % (item.get('done', 0), item.get('lines', 0)))
        imgui.same_line()
        raw().text_unformatted('%s — %s' % (item.get('name', item['id']), item.get('created', '')))
        if item.get('failed'):
            imgui.same_line()
            raw().text_disabled(tr('%d failed') % item['failed'])
        imgui.same_line()
        if widgets.small_button('Open the folder'):
            open_path(item['folder'])
        if not item.get('complete'):
            imgui.same_line()
            if widgets.small_button('Check what is left'):
                launch(app, 'speak_batch', {'resume': item['id'], 'dry_run': True,
                                            'device': state['device']}, 'batch_check')
            imgui.same_line()
            if widgets.small_button('Resume', 'confirm'):
                launch(app, 'speak_batch', {
                    'resume': item['id'], 'device': state['device'], 'seed': int(state['seed']),
                    'batch_size': 0 if state['auto'] else int(state['size'])}, 'speak_batch')
        imgui.pop_id()


def batch_tab(app):
    state = form(app)
    raw().text_wrapped(tr(
        'Speak a whole list of lines in one go. The lines are generated many at a time in one '
        'copy of the voice model, as many as the free graphics memory holds, so a large GPU '
        'rented by the hour is used to the full. Each task gets its own folder in '
        'data/batches: its characters, the list as given, one WAV per line named after its '
        'id in voix/, and resultats.csv. Tasks started while another runs wait their turn.'))
    height = max(430.0, raw().get_content_region_avail().y - raw().get_frame_height_with_spacing())
    imgui.begin_child('batch-body', (0, height), imgui.ChildFlags_.borders)
    _help()
    imgui.separator_text(tr('New task'))
    _settings(app, state)
    _personas(state)
    ready = bool(state['file'].strip()) if state['source'] == 0 else bool(state['text'].strip())
    imgui.begin_disabled(not ready)
    if widgets.button('Check the task'):
        launch(app, *request(state, dry_run=True), 'batch_check')
    imgui.same_line()
    if widgets.button('Queue the task' if app.busy else 'Start the task', 'confirm'):
        launch(app, *request(state), 'speak_batch')
    imgui.end_disabled()
    if not ready:
        raw().text_disabled(tr('Give a batch file or type a script first.'))
    _preview(state)
    _last(state)
    _listing(app, state)
    imgui.end_child()
