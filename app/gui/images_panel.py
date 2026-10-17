"""Reference photographs inside the Appearance tab.

Thumbnails are decoded once and cached by file path, so drawing the sheet every frame does
not re-read the pictures. A photograph that has gone missing is said to be missing rather
than silently skipped.
"""
from pathlib import Path

from cytools_core import CyToolError
from imgui_bundle import hello_imgui
import cyui
from ui_common import imgui, raw, tr

from personarp.paths import DATA

from . import widgets
from .state import open_path

ROLES = ['portrait', 'full_body', 'outfit', 'detail', 'expression', 'setting', 'reference']
ROLE_CAPTIONS = ['Portrait', 'Full body', 'Outfit', 'Detail', 'Expression', 'Setting',
                 'Reference']
THUMBNAIL = 132.0


def _thumbnail(path):
    """Texture and displayed size for one picture, or None when it cannot be shown."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    try:
        image = hello_imgui.image_and_size_from_encoded_data(data, cache_key=str(path))
    except Exception:                                     # noqa: BLE001 - a bad file is not fatal
        return None
    if image.size.x <= 0 or image.size.y <= 0:
        return None
    size = hello_imgui.image_proportional_size(imgui.ImVec2(THUMBNAIL, THUMBNAIL), image.size)
    # imgui.image takes a texture reference, not the raw id the loader hands back.
    return imgui.ImTextureRef(image.texture_id), size


def references(app, persona):
    """The photographs of a sheet: add, caption, describe, remove."""
    widgets.hint(tr('Kept with the character and carried by an export. They are your '
                    'reference, and the material the vision model reads to fill this tab. '
                    'The roleplay model never sees them.'))

    changed = False
    items = list(persona.get('references') or [])
    for index, item in enumerate(items):
        imgui.push_id('ref-%d' % index)
        path = item.get('file', '')
        thumbnail = _thumbnail(path)
        cyui.space(4.0)
        cyui.begin_card('reference', '')
        if thumbnail is not None:
            texture, size = thumbnail
            imgui.image(texture, size)
            imgui.same_line(0.0, cyui.dp(12.0))
        imgui.begin_group()
        if thumbnail is None:
            cyui.badge(tr('Picture missing from disk'), 'error')
        cyui.text_faint('%s · %d×%d · %.1f MB' % (Path(path).name, item.get('width', 0),
                                                  item.get('height', 0),
                                                  item.get('bytes', 0) / 1e6))
        with widgets.properties('##reference-fields', 110.0):
            changed |= widgets.combo(item, 'role', 'Shows', ROLES, ROLE_CAPTIONS)
            changed |= widgets.text_field(item, 'caption', 'Caption')
        imgui.begin_disabled(app.busy)
        if cyui.icon_text_button(cyui.icon.lightbulb,
                                 tr('Describe the character from this photo'), 'outline'):
            app.submit('describe_image', {'persona_id': app.persona_id, 'file': path,
                                          'keep_loaded': False}, 'describe_image')
        imgui.same_line()
        if widgets.icon_button(cyui.icon.zoom_in, 'See it large'):
            app.viewing = path
        imgui.same_line()
        if widgets.icon_button(cyui.icon.open_file, 'Open'):
            open_path(path)
        imgui.same_line()
        removed = widgets.icon_button(cyui.icon.trash, 'Move to trash')
        imgui.end_disabled()
        imgui.end_group()
        cyui.end_card()
        imgui.pop_id()
        if removed:
            try:
                app.call('remove_persona_image', {'persona_id': app.persona_id, 'file': path},
                         timeout=60)
                app.notice = 'Photograph moved to the character image trash.'
                app.load_persona()
                app.refresh_images()
                return changed
            except CyToolError as exc:
                app.error = str(exc)

    if changed:
        persona['references'] = items

    state = getattr(app, 'add_image', None)
    if state is None:
        state = app.add_image = {'path': '', 'role': 'portrait', 'caption': ''}
    cyui.space(6.0)
    cyui.overline(tr('Add a photograph').upper())
    with widgets.properties('##add-reference'):
        widgets.row('File (full path, or a file in data/inputs)')
        raw().set_next_item_width(-imgui.get_frame_height() - cyui.dp(8.0))
        _, state['path'] = raw().input_text('##reference-path', state['path'])
        imgui.same_line()
        if widgets.icon_button(cyui.icon.folder, 'Open data/inputs'):
            open_path(DATA / 'inputs')
        widgets.combo(state, 'role', 'What it shows', ROLES, ROLE_CAPTIONS)
        widgets.text_field(state, 'caption', 'Caption')
    imgui.begin_disabled(app.busy or not state['path'].strip())
    if cyui.icon_text_button(cyui.icon.add, tr('Add this photograph'), 'outline'):
        try:
            app.call('add_persona_image', {'persona_id': app.persona_id, 'image': state['path'],
                                           'role': state['role'], 'caption': state['caption']},
                     timeout=120)
            state['path'] = ''
            state['caption'] = ''
            app.notice = 'Photograph added to the sheet.'
            app.load_persona()
            app.refresh_images()
        except CyToolError as exc:
            app.error = str(exc)
    imgui.end_disabled()

    vision = [m for m in app.models if m.get('installed') and m.get('vision')]
    if not vision:
        cyui.callout('info', tr('No vision model is installed, so a photograph cannot be read '
                                'yet. Install one in Models.'))
    return changed
