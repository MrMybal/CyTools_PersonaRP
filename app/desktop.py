"""Dear ImGui window for CyTools_PersonaRP.

Every business action is a job submitted to the same Runtime the CLI and MCP use. No model
is loaded in this process, and closing or cancelling waits for the worker to really stop.
"""
import json
import os
import sys
import traceback
from pathlib import Path

from imgui_bundle import hello_imgui

import cyui
from ui_common import (imgui, raw, tr, run, configure_generation, system_pages, use_shell,
                       label as raw_label)

from personarp.paths import DATA, SETTINGS, ensure_data_layout, read_json, write_json
from tool import create_runtime

from gui import panels
from gui.batch_panel import batch_tab, form as batch_form
from gui.voice_panel import voice_tab
from gui.state import App, shown

WINDOW_TITLE = 'CyTools PersonaRP — Persistent characters'


def local_actor(runtime):
    """A credential stored for this machine, protected by the OS where that is available."""
    path = SETTINGS / 'desktop-credential.bin'

    def encode(value):
        if os.name == 'nt':
            import win32crypt
            return win32crypt.CryptProtectData(value, None, None, None, None, 0)
        return value

    def decode(value):
        if os.name == 'nt':
            import win32crypt
            return win32crypt.CryptUnprotectData(value, None, None, None, 0)[1]
        return value

    if path.exists():
        try:
            return runtime.authenticate(decode(path.read_bytes()).decode())
        except Exception:                                   # noqa: BLE001 - re-enrol below
            pass
    client = runtime.create_client('Desktop', ['network', 'filesystemExternal'])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(client['token'].encode()))
    if os.name != 'nt':
        path.chmod(0o600)
    return runtime.authenticate(client['token'])


def main():
    ensure_data_layout()
    if '--smoke-language' in sys.argv:
        # A screenshot run in another language; your saved preference is not touched.
        from ui_common import preferences
        preferences.values['language'] = sys.argv[sys.argv.index('--smoke-language') + 1]
    from branding import configure as configure_branding
    configure_branding('Cyberalien.CyTools_PersonaRP')
    runner = hello_imgui.RunnerParams()
    runner.app_window_params.window_title = WINDOW_TITLE
    runner.app_window_params.window_geometry.size = (1240, 980)
    runner.ini_filename = str(SETTINGS / 'imgui.ini')
    # CyUI shell: top bar, sidebar, status bar, and the page in the rest of the window.
    runner.imgui_window_params.default_imgui_window_type = \
        hello_imgui.DefaultImGuiWindowType.no_default_window
    use_shell()
    frames = 0
    smoke_tab = sys.argv[sys.argv.index('--smoke-tab') + 1] if '--smoke-tab' in sys.argv else ''

    with create_runtime(DATA / 'jobs') as runtime:
        actor = local_actor(runtime)
        session = runtime.create_session(actor, temporary=False)['sessionId']
        app = App(runtime, actor, session)
        if '--smoke-persona' in sys.argv:
            # Acceptance runs photograph a throwaway character; your selection is untouched.
            app.ephemeral = True
            app.persona_id = sys.argv[sys.argv.index('--smoke-persona') + 1]
            app.session_id = ''
            app.load_persona()
            if '--smoke-session' in sys.argv:
                app.session_id = sys.argv[sys.argv.index('--smoke-session') + 1]
                app.reload_conversation()
        configure_generation(runtime, app.capture_config, app.restore_config)
        # Acceptance runs check a batch in the window: the table of the dry run is drawn.
        smoke_batch = sys.argv[sys.argv.index('--smoke-batch') + 1] \
            if '--smoke-batch' in sys.argv else ''
        if smoke_batch:
            form = batch_form(app)
            form['source'], form['text'] = 1, Path(smoke_batch).read_text(encoding='utf-8')
            app.pending.append(('speak_batch', {'text': form['text'], 'dry_run': True},
                                'batch_check'))
        shot = {'taken': False}
        app.pending.append(('list_models', {'verify': False}, 'list_models'))
        if app.updates.get('auto_check') or app.updates.get('auto_download'):
            action = 'download' if app.updates.get('auto_download') else 'check'
            app.pending.append(('update', {'kind': 'engine', 'action': action}, 'update'))
            if app.updates.get('repository'):
                app.pending.append(('update', {'kind': 'app', 'action': action,
                                               'repository': app.updates['repository']}, 'update'))

        # The pages, grouped as the sidebar shows them. The key is the English caption, which
        # is also what --smoke-tab names.
        pages = [
            ('Roleplay', [('Scene', cyui.icon.people, panels.conversation,
                       'Play a scene with the selected character')]),
            ('Create', [('Characters', cyui.icon.contact, panels.characters,
                         'Sheets: identity, appearance, voice, model'),
                        ('Worlds', cyui.icon.globe, panels.worlds,
                         'Shared lore, places, factions and terms'),
                        ('Assistant', cyui.icon.lightbulb, panels.assistant,
                         'Draft a sheet, a world or a section')]),
            ('Voice', [('Voice', cyui.icon.microphone, voice_tab,
                        'Stable voices, speech engine and speech models'),
                       ('Batches', cyui.icon.list, batch_tab,
                        'Speak lists of lines into task folders')]),
            ('Library', [('Library', cyui.icon.library, panels.library_tab,
                          'Examples, pictures, export and import, ComfyUI'),
                         ('Models', cyui.icon.download, panels.models_tab,
                          'Conversation and vision models')]),
            ('System', [('Updates', cyui.icon.sync, panels.updates_tab,
                         'Application, engine and model updates'),
                        ('Diagnostics', cyui.icon.repair, panels.diagnostics,
                         'Engine, GPU and models, as this machine sees them')]),
        ]
        known = [caption for _, items in pages for caption, *_ in items] + [
            key for key, *_ in system_pages()]
        view = {'page': smoke_tab if smoke_tab in known else 'Scene', 'notice': ''}

        def top_bar():
            if cyui.begin_top_bar('##personarp-top'):
                cyui.heading('PersonaRP', 2)
                imgui.same_line(0.0, cyui.dp(18.0))
                imgui.begin_disabled(app.busy)
                identifiers = [entry['id'] for entry in app.personas]
                if identifiers:
                    index = identifiers.index(app.persona_id) if app.persona_id in identifiers else 0
                    captions = ['%s%s' % (entry['name'],
                                          '  ·  ' + entry['world_id'] if entry.get('world_id') else '')
                                for entry in app.personas]
                    raw().align_text_to_frame_padding()
                    cyui.text_dim(tr('Character'))
                    imgui.same_line()
                    raw().set_next_item_width(cyui.dp(300.0))
                    changed, index = raw().combo('##character', index, captions)
                    if changed:
                        app.select_persona(identifiers[index])
                else:
                    raw().align_text_to_frame_padding()
                    cyui.text_faint(tr('No character yet — create one in Characters.'))
                imgui.end_disabled()
                # Unsaved edits are visible from every page: they are written automatically
                # before anything runs, and saying so avoids the doubt that made it necessary.
                if app.dirty or app.world_dirty:
                    imgui.same_line(0.0, cyui.dp(14.0))
                    cyui.status_dot(cyui.palette().warning,
                                    tr('Unsaved edits — they are written before the next action'))
                    imgui.same_line()
                    if cyui.button(raw_label('Save now'), 'outline'):
                        app.flush()
                        app.notice = 'Saved.'
                if app.busy:
                    progress = app.job.get('progress') or {}
                    step = shown(progress.get('currentStep', 'waiting'))
                    width = cyui.dp(340.0)
                    imgui.same_line()
                    cyui.align_right(width + imgui.get_frame_height() * 2 + cyui.dp(16.0))
                    cyui.spinner('##busy', 8.0)
                    imgui.same_line()
                    cyui.progress_bar(progress.get('percent', 0) / 100.0, (width, 0.0),
                                      '%s — %s' % (tr(app.job['state']), step))
                    imgui.same_line()
                    if cyui.icon_button(cyui.icon.stop, tr('Cancel — the worker must really stop '
                                                          'before its resources are released')):
                        app.cancel()
            cyui.end_top_bar()

        def status_bar():
            if cyui.begin_status_bar('##personarp-status'):
                if app.job:
                    tone = {'Failed': 'error', 'Cancelled': 'warning'}.get(app.job['state'], 'neutral')
                    cyui.status_text(tone, tr('Last operation: ') + app.purpose + ' — '
                                     + tr(app.job['state']))
                    imgui.same_line(0.0, cyui.dp(16.0))
                if app.notice:
                    cyui.status_text('neutral', shown(app.notice).splitlines()[0][:160])
            cyui.end_status_bar()

        def player_bar():
            player = app.player
            if player is None or not player.loaded:
                return
            if cyui.begin_bottom_bar('##personarp-player'):
                if cyui.icon_button(cyui.icon.pause if player.playing else cyui.icon.play,
                                    tr('Pause') if player.playing else tr('Play')):
                    player.pause() if player.playing else player.play()
                imgui.same_line()
                if cyui.icon_button(cyui.icon.stop, tr('Stop')):
                    player.stop()
                imgui.same_line()
                raw().set_next_item_width(cyui.dp(360.0))
                changed, seconds = raw().slider_float('##position', player.seconds, 0.0,
                                                      max(0.1, player.duration), '%.1f s')
                if changed:
                    player.seek(seconds)
                imgui.same_line()
                raw().set_next_item_width(cyui.dp(140.0))
                _, player.volume = raw().slider_float('##volume', player.volume, 0.0, 1.0,
                                                      tr('volume %.2f'))
                imgui.same_line()
                raw().align_text_to_frame_padding()
                cyui.text_faint(Path(player.path).name)
            cyui.end_bottom_bar()

        def sidebar(system):
            if cyui.begin_sidebar('##personarp-nav', 200.0):
                cyui.sidebar_header('PERSONARP')
                for group, items in pages:
                    cyui.sidebar_group(tr(group).upper())
                    for caption, glyph, _, _ in items:
                        if cyui.sidebar_item(glyph, tr(caption), view['page'] == caption):
                            view['page'] = caption
                cyui.sidebar_group(tr('Tool').upper())
                for key, caption, glyph, _ in system:
                    if cyui.sidebar_item(glyph, tr(caption), view['page'] == key):
                        view['page'] = key
            cyui.end_sidebar()

        def page(system):
            viewport = raw().get_main_viewport()
            raw().set_next_window_pos(viewport.work_pos)
            raw().set_next_window_size(viewport.work_size)
            flags = (raw().WindowFlags_.no_decoration | raw().WindowFlags_.no_saved_settings
                     | raw().WindowFlags_.no_bring_to_front_on_focus)
            with cyui.scoped_var(raw().StyleVar_.window_padding, cyui.dp2(18.0, 14.0)):
                raw().begin('##personarp-page', None, flags)
            if app.error:
                cyui.callout('error', shown(app.error)
                             + ('  [%s]' % app.error_code if getattr(app, 'error_code', '') else ''))
                if cyui.button(raw_label('Dismiss##error'), 'ghost', small=True):
                    app.error = ''
                    app.error_code = ''
                cyui.space(6.0)
            drawn = False
            for _, items in pages:
                for caption, _, drawer, subtitle in items:
                    if caption == view['page']:
                        cyui.panel_header(tr(caption), tr(subtitle))
                        cyui.divider(4.0)
                        run_page(caption, lambda: drawer(app))
                        drawn = True
            for key, caption, _, drawer in system:
                if key == view['page'] and not drawn:
                    cyui.panel_header(tr(caption))
                    cyui.divider(4.0)
                    run_page(caption, drawer)
            raw().end()

        def run_page(caption, draw):
            try:
                draw()
            except Exception as exc:            # noqa: BLE001 - a page must not kill the window
                app.error = '%s: %s' % (caption, exc)
                if '--strict-ui' in sys.argv:
                    raise

        def gui():
            nonlocal frames
            frames += 1
            app.poll()
            # A notice is an event: it is shown once as a toast, and stays in the status bar.
            if app.notice and app.notice != view['notice']:
                cyui.notify(shown(app.notice), 'neutral')
            view['notice'] = app.notice
            system = system_pages()
            top_bar()
            status_bar()
            player_bar()
            sidebar(system)
            page(system)
            cyui.render_notifications()

            waited = not smoke_batch or app.batch_form.get('preview') is not None \
                or frames > 900
            if smoke_tab and frames >= 12 and not shot['taken'] and waited:
                _screenshot(smoke_tab, runner)
                shot['taken'] = True
            if ('--smoke-test' in sys.argv or smoke_tab) and frames > 14 and not app.busy \
                    and (shot['taken'] or not smoke_tab):
                runner.app_shall_exit = True

        runner.callbacks.show_gui = gui
        try:
            run(runner)
        finally:
            app.stop_audio()
            app.persist()
            if app.job and app.job['state'] not in ('Completed', 'Cancelled', 'Failed'):
                app.cancel()


def _screenshot(name, runner):
    """Deferred: hello_imgui only exposes the window image once the loop has drawn it."""
    runner.app_shall_exit = True


def capture(name):
    """Write the final window image as a PNG, for the validation report."""
    import struct
    import zlib
    image = hello_imgui.final_app_window_screenshot()
    height, width, channels = image.shape
    pixels = image.tobytes()

    def chunk(kind, data):
        return (struct.pack('!I', len(data)) + kind + data
                + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff))

    rows = b''.join(b'\0' + pixels[y * width * channels:(y + 1) * width * channels]
                    for y in range(height))
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6 if channels == 4 else 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
    target = DATA / 'reports' / ('ui-' + name.replace(' ', '-').lower() + '.png')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png)
    return target


if __name__ == '__main__':
    try:
        main()
        if '--smoke-tab' in sys.argv:
            # One screenshot per section, not one per tab, or five sheet runs overwrite
            # each other and only the last is evidence of anything.
            name = sys.argv[sys.argv.index('--smoke-tab') + 1]
            if '--smoke-sheet' in sys.argv:
                name += '-' + sys.argv[sys.argv.index('--smoke-sheet') + 1]
            if '--smoke-name' in sys.argv:
                name = sys.argv[sys.argv.index('--smoke-name') + 1]
            if '--smoke-language' in sys.argv:
                name = sys.argv[sys.argv.index('--smoke-language') + 1] + '-' + name
            print(capture(name))
    except BaseException:
        path = DATA / 'logs' / 'desktop-error.log'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(traceback.format_exc(), encoding='utf-8')
        raise
