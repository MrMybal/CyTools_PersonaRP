---
id: operation-comfyui-nodes-status
title: comfyui_nodes_status
description: The ComfyUI installations found on this machine (Comfy Desktop), plus comfyuipath when given, each with whether the PersonaRP nodes are installed and up to date.
section: Reference
order: 200
parent: operations
revision: c2ed67316642a871
---

The ComfyUI installations found on this machine (Comfy Desktop), plus comfyui_path when given, each with whether the PersonaRP nodes are installed and up to date.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `comfyui_path` | `string` | No | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `comfyui` | `array` | No | See the operation parameters.  |
| `nodes` | `array` | No | See the operation parameters.  |
| `packDigest` | `string` | No | See the operation parameters.  |
| `toolRoot` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation comfyui_nodes_status
```
