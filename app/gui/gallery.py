"""Seeing the pictures: a large view, and a gallery of everything the library holds.

Thumbnails on a sheet tell you a picture exists; they do not let you look at it. This draws
the selected picture as large as the pane allows, and lists every photograph of every
character so the library can be browsed as a library.
"""
from pathlib import Path

from cytools_core import CyToolError
from imgui_bundle import hello_imgui
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
    imgui.separator_text(tr('Picture'))
    available = imgui.get_content_region_avail()
    drawn = texture(path, (max(220.0, available.x - 20.0), height))
    if drawn is None:
        imgui.text_colored(imgui.ImVec4(1, 0.6, 0.6, 1),
                           tr('This picture can no longer be read: ') + str(path))
    else:
        handle, size = drawn
        imgui.image(handle, size)
        raw().text_disabled('%s  ·  %.0f×%.0f' % (Path(path).name, size.x, size.y))
    if widgets.button('Open outside##viewer'):
        open_path(path)
    imgui.same_line()
    if widgets.button('Close the picture'):
        app.viewing = ''


def contact_sheet(app, items, columns=6):
    """A grid of small pictures; clicking one opens it in the viewer."""
    if not items:
        raw().text_disabled(tr('No photograph in the library yet. Add one on a character, in '
                               'Appearance.'))
        return
    for index, item in enumerate(items):
        if index % columns:
            imgui.same_line()
        imgui.push_id('contact-%d' % index)
        imgui.begin_group()
        path = item.get('file', '')
        drawn = texture(path, (CONTACT, CONTACT)) if item.get('present', True) else None
        if drawn is None:
            widgets.button(tr('missing') + '##%d' % index, (CONTACT, CONTACT))
        else:
            handle, size = drawn
            if imgui.image_button('##picture-%d' % index, handle, size):
                app.viewing = path
        caption = item.get('persona_name') or Path(path).stem
        raw().text_disabled(caption[:16])
        imgui.end_group()
        imgui.pop_id()
    imgui.new_line()


def library_gallery(app):
    """Every photograph of every character, with the one being looked at underneath."""
    imgui.separator_text(tr('Picture library'))
    imgui.begin_disabled(app.busy)
    if widgets.button('Refresh the pictures'):
        app.refresh_images()
    imgui.end_disabled()
    imgui.same_line()
    only_current = getattr(app, 'gallery_current_only', False)
    _, only_current = imgui.checkbox(tr('Only the selected character'), only_current)
    app.gallery_current_only = only_current

    items = app.images
    if only_current and app.persona_id:
        items = [item for item in items if item.get('persona_id') == app.persona_id]
    missing = [item for item in items if not item.get('present', True)]
    raw().text_disabled(tr('%d picture(s), %d character(s)%s')
                        % (len(items), len({item.get('persona_id') for item in items}),
                           tr(', %d missing from disk') % len(missing) if missing else ''))

    imgui.begin_child('gallery', (0, 240), imgui.ChildFlags_.borders)
    contact_sheet(app, items)
    imgui.end_child()

    path = getattr(app, 'viewing', '')
    if path:
        entry = next((item for item in app.images if item.get('file') == path), None)
        if entry:
            role = entry.get('role', '')
            caption = dict(zip(ROLES, ROLE_CAPTIONS)).get(role, role)
            raw().text_wrapped('%s — %s%s' % (entry.get('persona_name', ''), tr(caption),
                                              '  ·  ' + entry['caption'] if entry.get('caption')
                                              else ''))
        viewer(app, height=360.0)
        imgui.begin_disabled(app.busy or not entry)
        if widgets.button('Describe the character from this picture##gallery') and entry:
            app.submit('describe_image', {'persona_id': entry['persona_id'], 'file': path},
                       'describe_image')
        imgui.end_disabled()
    else:
        raw().text_disabled(tr('Click a picture to see it here.'))
