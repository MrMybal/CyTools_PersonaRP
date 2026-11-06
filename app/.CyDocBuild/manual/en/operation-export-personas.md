---
id: operation-export-personas
title: export_personas
description: Write a self-contained bundle: the sheets, their world, their voice descriptors, and optionally the reference recordings as a .zip and the scenes played with them. An imported scene follows its character under a new identifier.
section: Reference
order: 200
parent: operations
revision: 1ae4b34fa5146ac0
---

Write a self-contained bundle: the sheets, their world, their voice descriptors, and optionally the reference recordings as a .zip and the scenes played with them. An imported scene follows its character under a new identifier.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_ids` | `array` | Yes | See the operation parameters. `default=[]` |
| `destination` | `string` | No | See the operation parameters. `default=""` |
| `include_world` | `boolean` | No | See the operation parameters. `default=true` |
| `include_voice` | `boolean` | No | See the operation parameters. `default=true` |
| `include_audio` | `boolean` | No | See the operation parameters. `default=false` |
| `include_images` | `boolean` | No | See the operation parameters. `default=true` |
| `include_sessions` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | No | See the operation parameters.  |
| `personas` | `array` | No | See the operation parameters.  |
| `worlds` | `array` | No | See the operation parameters.  |
| `voices` | `array` | No | See the operation parameters.  |
| `bundledAudio` | `integer` | No | See the operation parameters.  |
| `bundledImages` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation export_personas
```
