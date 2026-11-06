---
id: operation-scene-prompts
title: scene_prompts
description: Turn a directive into ready-to-use image and video prompts, filling anything the model left empty from the character sheet and the world. Renders nothing.
section: Reference
order: 200
parent: operations
revision: 2006757c0a6d7cbf
---

Turn a directive into ready-to-use image and video prompts, filling anything the model left empty from the character sheet and the world. Renders nothing.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `scene` | `object` | Yes | See the operation parameters. `default={}` |
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `world_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `targets` | `array` | No | See the operation parameters. `default=[]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `image_prompt` | `string` | No | See the operation parameters.  |
| `video_prompt` | `string` | No | See the operation parameters.  |
| `negative_prompt` | `string` | No | See the operation parameters.  |
| `renderings` | `object` | No | See the operation parameters.  |
| `summary` | `string` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation scene_prompts
```
