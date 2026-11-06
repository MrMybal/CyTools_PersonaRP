---
id: operation-install-comfyui-nodes
title: install_comfyui_nodes
description: Copy the PersonaRP nodes into the customnodes folder of a ComfyUI (its folder, its base directory or customnodes itself) with a config.json naming this Tool. The nodes use the Tool through its local API — they start it on port…
section: Reference
order: 200
parent: operations
revision: d43b9aa3721d1412
---

Copy the PersonaRP nodes into the custom_nodes folder of a ComfyUI (its folder, its base directory or custom_nodes itself) with a config.json naming this Tool. The nodes use the Tool through its local API — they start it on port `port` when it does not answer and auto_start is on — and never import it. Installing again replaces the copy; nothing else in ComfyUI is touched. Restart ComfyUI to load them.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `comfyui_path` | `string` | Yes | See the operation parameters. `default=""` |
| `port` | `integer` | No | See the operation parameters. `default=8791`, `minimum=1024`, `maximum=65535` |
| `auto_start` | `boolean` | No | See the operation parameters. `default=true` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `folder` | `string` | No | See the operation parameters.  |
| `files` | `integer` | No | See the operation parameters.  |
| `packDigest` | `string` | No | See the operation parameters.  |
| `toolRoot` | `string` | No | See the operation parameters.  |
| `port` | `integer` | No | See the operation parameters.  |
| `nodes` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_comfyui_nodes
```
