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

from ui_common import imgui, raw, tr, run, configure_generation

from personarp.paths import DATA, SETTINGS, ensure_data_layout, read_json, write_json
from tool import create_runtime

from gui import panels, widgets
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

        def gui():
            nonlocal frames
            frames += 1
            app.poll()

            imgui.text_colored(imgui.ImVec4(0.60, 0.80, 1, 1), 'PersonaRP')
            imgui.same_line()
            raw().text_disabled(tr('Local characters, worlds and scenes'))
            imgui.separator()

            # Character selector, visible from every tab.
            imgui.begin_disabled(app.busy)
            identifiers = [entry['id'] for entry in app.personas]
            if identifiers:
                index = identifiers.index(app.persona_id) if app.persona_id in identifiers else 0
                captions = ['%s%s' % (entry['name'],
                                      '  ·  ' + entry['world_id'] if entry.get('world_id') else '')
                            for entry in app.personas]
                changed, index = imgui.combo(tr('Character'), index, captions)
                if changed:
                    app.select_persona(identifiers[index])
            else:
                raw().text_disabled(tr('No character yet — create one in Characters.'))
            imgui.end_disabled()

            # Unsaved edits are visible from every tab, not buried in the sheet: they are
            # written automatically before anything runs, and saying so avoids the doubt
            # that made this necessary in the first place.
            if app.dirty or app.world_dirty:
                imgui.text_colored(imgui.ImVec4(1, 0.82, 0.4, 1),
                                   tr('Unsaved edits — they are written before the next action'))
                imgui.same_line()
                if widgets.button('Save now'):
                    app.flush()
                    app.notice = 'Saved.'

            # The bar belongs to work in progress; a finished job leaves a one-line status.
            if app.busy:
                progress = app.job.get('progress') or {}
                imgui.progress_bar(progress.get('percent', 0) / 100, (-1, 0),
                                   tr(app.job['state']) + ' — '
                                   + shown(progress.get('currentStep', 'waiting')))
            elif app.job:
                raw().text_disabled(tr('Last operation: ') + app.purpose + ' — '
                                    + tr(app.job['state']))
            if app.busy:
                if widgets.button('Cancel'):
                    app.cancel()
                imgui.same_line()
                raw().text_disabled(tr('The worker must really stop before its resources are '
                                       'released.'))
            if app.error:
                imgui.text_colored(imgui.ImVec4(1, 0.5, 0.5, 1), tr('Error'))
                raw().text_wrapped(shown(app.error))
                if getattr(app, 'error_code', ''):
                    raw().text_disabled('[%s]' % app.error_code)
                imgui.same_line()
                if widgets.button('Dismiss##error'):
                    app.error = ''
                    app.error_code = ''
            if app.notice:
                raw().text_wrapped(shown(app.notice))

            def tab(caption):
                flags = raw().TabItemFlags_.set_selected if smoke_tab == caption and frames < 4 else 0
                return imgui.begin_tab_item(caption, None, flags)

            if imgui.begin_tab_bar('main'):
                for caption, drawer in (('Scene', panels.conversation),
                                        ('Characters', panels.characters),
                                        ('Worlds', panels.worlds),
                                        ('Assistant', panels.assistant),
                                        ('Voice', voice_tab),
                                        ('Batches', batch_tab),
                                        ('Library', panels.library_tab),
                                        ('Models', panels.models_tab),
                                        ('Updates', panels.updates_tab),
                                        ('Diagnostics', panels.diagnostics)):
                    opened, _ = tab(caption)
                    if opened:
                        try:
                            drawer(app)
                        except Exception as exc:            # noqa: BLE001 - a panel must not kill the window
                            app.error = '%s: %s' % (caption, exc)
                            if '--strict-ui' in sys.argv:
                                raise
                        imgui.end_tab_item()
                imgui.end_tab_bar()

            player = app.player
            if player is not None and player.loaded:
                imgui.separator()
                imgui.text(tr('Audio'))
                imgui.same_line()
                if widgets.button('Pause' if player.playing else 'Play'):
                    player.pause() if player.playing else player.play()
                imgui.same_line()
                if widgets.button('Stop'):
                    player.stop()
                imgui.same_line()
                changed, seconds = imgui.slider_float('##position', player.seconds, 0.0,
                                                      max(0.1, player.duration), '%.1f s')
                if changed:
                    player.seek(seconds)
                imgui.same_line()
                _, player.volume = imgui.slider_float('##volume', player.volume, 0.0, 1.0,
                                                      tr('volume %.2f'))
                raw().text_disabled(Path(player.path).name)

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
