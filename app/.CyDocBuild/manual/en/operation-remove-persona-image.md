---
id: operation-remove-persona-image
title: remove_persona_image
description: Move a photograph to the character's image trash. Nothing is deleted.
section: Reference
order: 200
parent: operations
revision: ea848cb329757f69
---

Move a photograph to the character's image trash. Nothing is deleted.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `file` | `string` | Yes | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters. `default={}` |
| `references` | `array` | No | See the operation parameters.  |
| `trash` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_persona_image
```
