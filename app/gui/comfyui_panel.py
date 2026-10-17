"""Library > ComfyUI: install the PersonaRP nodes into a ComfyUI, and see where they are.

Everything goes through the comfyui_nodes_status and install_comfyui_nodes operations, the
same ones the CLI and MCP use.
"""
import cyui
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
    imgui.begin_child('comfyui-page', (0, 0), 0)
    widgets.hint(tr(
        'Nodes for ComfyUI: a character and what an image model needs to draw it, a dialogue '
        'with its image and video prompts, a voice, a translation, reading a photograph, a '
        'voice task, and any operation of the Tool. They use this Tool through its local API: '
        'ComfyUI keeps its own Python and PersonaRP its own, and PersonaRP only starts when one '
        'of its nodes runs.'))
    if state['status'] is None:
        refresh(app, state)
    status = state['status'] or {}

    widgets.section('ComfyUI found on this computer')
    found = [entry for entry in status.get('comfyui', []) if entry.get('source') != 'given']
    if not found:
        cyui.text_faint(tr('None found automatically (Comfy Desktop is looked for). Give the '
                           'folder of your ComfyUI below.'))
    imgui.begin_disabled(app.busy)
    for entry in found:
        imgui.push_id('comfyui-' + entry['path'])
        cyui.begin_card('comfyui', '')
        raw().align_text_to_frame_padding()
        cyui.heading(entry.get('name', 'ComfyUI'), 3)
        imgui.same_line()
        if entry.get('upToDate'):
            cyui.badge(tr('Installed, up to date'), 'success')
        elif entry.get('installed'):
            cyui.badge(tr('Installed, to update'), 'warning')
        else:
            cyui.badge(tr('Not installed'))
        cyui.text_faint('%s  (%s)' % (entry['path'], entry.get('source', '')))
        if cyui.icon_text_button(cyui.icon.download,
                                 tr('Update here' if entry.get('installed') else 'Install here'),
                                 'outline'):
            _install(app, state, entry['path'])
        if entry.get('installed'):
            imgui.same_line()
            if widgets.icon_button(cyui.icon.folder, 'Open the folder'):
                open_path(entry.get('folder', ''))
        cyui.end_card()
        cyui.space(4.0)
        imgui.pop_id()
    imgui.end_disabled()

    widgets.section('Another ComfyUI')
    dialog = state.get('dialog')
    if dialog is not None and dialog.ready():
        chosen = dialog.result()
        if chosen:
            state['path'] = chosen
            state['status'] = None
        state['dialog'] = None
    with widgets.properties('##comfyui-other'):
        widgets.row('ComfyUI folder')
        raw().set_next_item_width(-imgui.get_frame_height() - cyui.dp(8.0))
        _, state['path'] = raw().input_text('##comfyui-folder', state['path'])
        imgui.same_line()
        if widgets.icon_button(cyui.icon.open_file, 'Browse'):
            from imgui_bundle import portable_file_dialogs as pfd
            state['dialog'] = pfd.select_folder(tr('ComfyUI folder'))
        widgets.hint(tr('The folder that holds custom_nodes (a portable ComfyUI: its ComfyUI '
                        'subfolder), or custom_nodes itself.'))
        widgets.integer(state, 'port', 'Port of the local API', 1024, 8791)
        state['port'] = max(1024, min(65535, int(state['port'])))
        widgets.checkbox(state, 'auto_start', 'ComfyUI starts PersonaRP when a node needs it')
    given = next((entry for entry in status.get('comfyui', []) if entry.get('source') == 'given'),
                 None)
    if given and not given.get('valid'):
        cyui.callout('error', tr(given.get('reason', '')))
    imgui.begin_disabled(app.busy or not state['path'].strip())
    if cyui.icon_text_button(cyui.icon.download, tr('Install into this folder'), 'outline'):
        _install(app, state, state['path'].strip())
    imgui.end_disabled()
    imgui.same_line()
    if widgets.icon_button(cyui.icon.refresh, 'Refresh'):
        state['status'] = None

    widgets.section('The nodes')
    flags = raw().TableFlags_.row_bg | raw().TableFlags_.borders_inner_h
    nodes = status.get('nodes', [])
    if nodes and raw().begin_table('##comfyui-nodes', 2, flags):
        raw().table_setup_column(tr('Node'), raw().TableColumnFlags_.width_stretch)
        raw().table_setup_column(tr('Identifier'), raw().TableColumnFlags_.width_stretch)
        raw().table_headers_row()
        for node in nodes:
            raw().table_next_row()
            raw().table_set_column_index(0)
            raw().text_unformatted(node['name'])
            raw().table_set_column_index(1)
            cyui.text_faint(node['id'])
        raw().end_table()
    cyui.space(4.0)
    cyui.callout('info', tr('Restart ComfyUI after installing or updating: it loads its nodes '
                            'when it starts. They are in the CyTools/PersonaRP category.'))
    imgui.end_child()
