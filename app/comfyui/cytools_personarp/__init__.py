"""CyTools PersonaRP nodes for ComfyUI.

Installed by PersonaRP itself (Library > ComfyUI, or the install_comfyui_nodes operation),
which writes config.json with the place of the Tool. The nodes then use the Tool through its
local API; see client.py.
"""
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
