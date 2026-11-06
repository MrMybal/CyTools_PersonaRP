---
id: operation-apply-proposal
title: apply_proposal
description: Merge a proposal into a stored character or world. Only the targeted section is replaced; a new revision is written and the previous one is kept.
section: Reference
order: 200
parent: operations
revision: d0ccf851122d5b5c
---

Merge a proposal into a stored character or world. Only the targeted section is replaced; a new revision is written and the previous one is kept.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `world_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `target` | `string` | No | See the operation parameters. `default="sheet"`, `enum=["appearance", "background", "canon", "dialogues", "factions", "glossary", "history", "identity", "locations", "media", "memory", "notes", "personality", "rules", "setting", "sheet", "speech", "state", "world"]` |
| `kind` | `string` | No | See the operation parameters. `default="persona"`, `enum=["persona", "world"]` |
| `proposal` | `object/array/string` | Yes | See the operation parameters.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `document` | `object` | No | See the operation parameters.  |
| `id` | `string` | No | See the operation parameters.  |
| `revision` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation apply_proposal
```
