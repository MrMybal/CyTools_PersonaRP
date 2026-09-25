"""Library > ComfyUI: install the PersonaRP nodes into a ComfyUI, and see where they are.

Everything goes through the comfyui_nodes_status and install_comfyui_nodes operations, the
same ones the CLI and MCP use.
"""
from ui_common import imgui, raw, tr

from . import widgets
from .state import open_path


def _state(app):
    state = getattr(app, 'comfyui_state', None)
    if state is None:
        state = app.comfyui_state = {'path': '', 'port': 8791, 'auto_start': True,
                                     'status': None, 'dialog': None}
    return state


def refresh(app, state):
    try:
        state['status'] = app.call('comfyui_nodes_status', {'comfyui_path': state['path'].strip()},
                                   flush=False)
    except Exception as exc:                                    # noqa: BLE001 - shown to the user
        app.error = str(exc)
        state['status'] = {'comfyui': [], 'nodes': []}


def _install(app, state, path):
    app.submit('install_comfyui_nodes', {'comfyui_path': path, 'port': int(state['port']),
                                         'auto_start': bool(state['auto_start'])},
               'install_comfyui')


def comfyui_tab(app):
    state = _state(app)
    raw().text_wrapped(tr(
        'Nodes for ComfyUI: a character and what an image model needs to draw it, a dialogue '
        'with its image and video prompts, a voice, a translation, reading a photograph, a '
        'voice task, and any operation of the Tool. They use this Tool through its local API: '
        'ComfyUI keeps its own Python and PersonaRP its own, and PersonaRP only starts when one '
        'of its nodes runs.'))
    if state['status'] is None:
        refresh(app, state)
    status = state['status'] or {}

    imgui.separator_text(tr('ComfyUI found on this computer'))
    found = [entry for entry in status.get('comfyui', []) if entry.get('source') != 'given']
    if not found:
        raw().text_disabled(tr('None found automatically (Comfy Desktop is looked for). Give the '
                               'folder of your ComfyUI below.'))
    imgui.begin_disabled(app.busy)
    for entry in found:
        imgui.push_id('comfyui-' + entry['path'])
        if entry.get('upToDate'):
            imgui.text_colored(imgui.ImVec4(0.45, 0.85, 0.5, 1.0), tr('Installed, up to date'))
        elif entry.get('installed'):
            imgui.text_colored(imgui.ImVec4(1.0, 0.75, 0.35, 1.0), tr('Installed, to update'))
        else:
            raw().text_disabled(tr('Not installed'))
        imgui.same_line()
        raw().text_unformatted('%s — %s (%s)' % (entry.get('name', 'ComfyUI'), entry['path'],
                                                 entry.get('source', '')))
        imgui.same_line()
        if widgets.small_button('Update here' if entry.get('installed') else 'Install here',
                                'confirm'):
            _install(app, state, entry['path'])
        if entry.get('installed'):
            imgui.same_line()
            if widgets.small_button('Open the folder'):
                open_path(entry.get('folder', ''))
        imgui.pop_id()
    imgui.end_disabled()

    imgui.separator_text(tr('Another ComfyUI'))
    dialog = state.get('dialog')
    if dialog is not None and dialog.ready():
        chosen = dialog.result()
        if chosen:
            state['path'] = chosen
            state['status'] = None
        state['dialog'] = None
    _, state['path'] = imgui.input_text('ComfyUI folder', state['path'])
    imgui.same_line()
    if widgets.button('Browse##comfyui'):
        from imgui_bundle import portable_file_dialogs as pfd
        state['dialog'] = pfd.select_folder(tr('ComfyUI folder'))
    raw().text_disabled(tr('The folder that holds custom_nodes (a portable ComfyUI: its ComfyUI '
                           'subfolder), or custom_nodes itself.'))
    _, state['port'] = imgui.input_int('Port of the local API', int(state['port']))
    state['port'] = max(1024, min(65535, state['port']))
    _, state['auto_start'] = imgui.checkbox('ComfyUI starts PersonaRP when a node needs it',
                                            state['auto_start'])
    given = next((entry for entry in status.get('comfyui', []) if entry.get('source') == 'given'),
                 None)
    if given and not given.get('valid'):
        imgui.text_colored(imgui.ImVec4(1.0, 0.55, 0.45, 1.0), tr(given.get('reason', '')))
    imgui.begin_disabled(app.busy or not state['path'].strip())
    if widgets.button('Install into this folder', 'confirm'):
        _install(app, state, state['path'].strip())
    imgui.end_disabled()
    imgui.same_line()
    if widgets.button('Refresh##comfyui'):
        state['status'] = None

    imgui.separator_text(tr('The nodes'))
    for node in status.get('nodes', []):
        raw().bullet_text('%s  (%s)' % (node['name'], node['id']))
    raw().text_disabled(tr('Restart ComfyUI after installing or updating: it loads its nodes '
                           'when it starts. They are in the CyTools/PersonaRP category.'))
