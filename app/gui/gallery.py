"""Seeing the pictures: a large view, and a gallery of everything the library holds.

Thumbnails on a sheet tell you a picture exists; they do not let you look at it. This draws
the selected picture as large as the pane allows, and lists every photograph of every
character so the library can be browsed as a library.
"""
from pathlib import Path

from cytools_core import CyToolError
from imgui_bundle import hello_imgui
import cyui
from . import widgets
from .images_panel import ROLE_CAPTIONS, ROLES
from ui_common import imgui, raw, tr

from .state import open_path

THUMBNAIL = 132.0
CONTACT = 96.0


def texture(path, box):
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
    size = hello_imgui.image_proportional_size(imgui.ImVec2(box[0], box[1]), image.size)
    return imgui.ImTextureRef(image.texture_id), size


def viewer(app, height=440.0):
    """The picture currently being looked at, as big as the pane allows."""
    path = getattr(app, 'viewing', '')
    if not path:
        return
    cyui.space(4.0)
    cyui.begin_card('viewer', '')
    raw().align_text_to_frame_padding()
    cyui.text_dim(Path(path).name)
    imgui.same_line()
    cyui.align_right(imgui.get_frame_height() * 2 + cyui.dp(8.0))
    if widgets.icon_button(cyui.icon.open_file, 'Open outside'):
        open_path(path)
    imgui.same_line()
    if widgets.icon_button(cyui.icon.close, 'Close the picture'):
        app.viewing = ''
    available = imgui.get_content_region_avail()
    drawn = texture(path, (max(220.0, available.x - 20.0), height))
    if drawn is None:
        cyui.callout('error', tr('This picture can no longer be read: ') + str(path))
    else:
        handle, size = drawn
        imgui.image(handle, size)
        cyui.text_faint('%.0f×%.0f' % (size.x, size.y))
    cyui.end_card()


def contact_sheet(app, items, columns=0):
    """A grid of small pictures; clicking one opens it in the viewer."""
    if not items:
        widgets.empty('No photograph yet',
                      'Add one on a character, in Characters > Appearance.', cyui.icon.photo)
        return
    style = raw().get_style()
    cell = cyui.dp(CONTACT) + style.frame_padding.x * 2 + style.item_spacing.x
    columns = columns or max(1, int(imgui.get_content_region_avail().x // cell))
    current = getattr(app, 'viewing', '')
    p = cyui.palette()
    for index, item in enumerate(items):
        if index % columns:
            imgui.same_line()
        imgui.push_id('contact-%d' % index)
        imgui.begin_group()
        path = item.get('file', '')
        drawn = texture(path, (cyui.dp(CONTACT), cyui.dp(CONTACT))) \
            if item.get('present', True) else None
        if drawn is None:
            cyui.button(tr('missing') + '##%d' % index, 'danger',
                        (cyui.dp(CONTACT) + style.frame_padding.x * 2,
                         cyui.dp(CONTACT) + style.frame_padding.y * 2))
        else:
            handle, size = drawn
            selected = path == current
            with cyui.scoped_color(raw().Col_.button, p.accent if selected else p.bg2):
                if imgui.image_button('##picture-%d' % index, handle, size):
                    app.viewing = path
        caption = item.get('persona_name') or Path(path).stem
        cyui.tooltip(caption)
        cyui.text_faint(caption[:16])
        imgui.end_group()
        imgui.pop_id()


def library_gallery(app):
    """Every photograph of every character, with the one being looked at underneath."""
    imgui.begin_disabled(app.busy)
    if widgets.icon_button(cyui.icon.refresh, 'Refresh the pictures'):
        app.refresh_images()
    imgui.end_disabled()
    imgui.same_line()
    only_current = getattr(app, 'gallery_current_only', False)
    _, only_current = cyui.toggle_switch(tr('Only the selected character'), only_current)
    app.gallery_current_only = only_current

    items = app.images
    if only_current and app.persona_id:
        items = [item for item in items if item.get('persona_id') == app.persona_id]
    missing = [item for item in items if not item.get('present', True)]
    imgui.same_line()
    text = tr('%d picture(s), %d character(s)%s') % (
        len(items), len({item.get('persona_id') for item in items}),
        tr(', %d missing from disk') % len(missing) if missing else '')
    cyui.align_right(raw().calc_text_size(text).x + cyui.dp(4.0))
    raw().align_text_to_frame_padding()
    cyui.text_faint(text)

    path = getattr(app, 'viewing', '')
    imgui.begin_child('gallery', (0, 0 if not path else cyui.dp(250.0)), 0)
    contact_sheet(app, items)
    imgui.end_child()

    if path:
        entry = next((item for item in app.images if item.get('file') == path), None)
        imgui.begin_child('gallery-picture', (0, 0), 0)
        if entry:
            role = entry.get('role', '')
            caption = dict(zip(ROLES, ROLE_CAPTIONS)).get(role, role)
            raw().align_text_to_frame_padding()
            cyui.heading(entry.get('persona_name', ''), 3)
            imgui.same_line()
            cyui.badge(tr(caption))
            if entry.get('caption'):
                imgui.same_line()
                cyui.text_dim(entry['caption'])
            imgui.same_line()
            imgui.begin_disabled(app.busy)
            if cyui.icon_text_button(cyui.icon.lightbulb,
                                     tr('Describe the character from this picture') + '##gallery',
                                     'outline'):
                app.submit('describe_image', {'persona_id': entry['persona_id'], 'file': path},
                           'describe_image')
            imgui.end_disabled()
        viewer(app, height=360.0)
        imgui.end_child()
