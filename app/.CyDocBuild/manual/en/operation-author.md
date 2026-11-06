---
id: operation-author
title: author
description: Write a character sheet, a world, or one section of either. The assistant never plays the character and never writes to the library; applyproposal does that explicitly.
section: Reference
order: 200
parent: operations
revision: 221e0c7f2140cc9d
---

Write a character sheet, a world, or one section of either. The assistant never plays the character and never writes to the library; apply_proposal does that explicitly.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `request` | `string` | Yes | See the operation parameters. `default=""` |
| `target` | `string` | No | See the operation parameters. `default="sheet"`, `enum=["appearance", "background", "canon", "dialogues", "factions", "glossary", "history", "identity", "locations", "media", "memory", "notes", "personality", "rules", "setting", "sheet", "speech", "state", "world"]` |
| `kind` | `string` | No | See the operation parameters. `default="persona"`, `enum=["persona", "world"]` |
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `world_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `thread_id` | `string` | No | See the operation parameters. `default=""` |
| `image` | `string` | No | See the operation parameters. `default=""` |
| `vision_model` | `string` | No | See the operation parameters. `default=""` |
| `language` | `string` | No | See the operation parameters. `default="Francais"` |
| `llm_model` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | Empty keeps the device recorded on the character sheet. `default=""`, `enum=["", "cpu", "cuda"]` |
| `temperature` | `number/null` | No | See the operation parameters. `default=null`, `minimum=0`, `maximum=2` |
| `response_length` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=16`, `maximum=4096` |
| `seed` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `threads` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=1`, `maximum=64` |
| `keep_loaded` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `proposal` | `object/array/string` | No | See the operation parameters.  |
| `raw` | `string` | No | See the operation parameters.  |
| `target` | `string` | No | See the operation parameters.  |
| `kind` | `string` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `picture` | `object` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation author
```
