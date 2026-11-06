---
id: operation-preview-prompt
title: preview_prompt
description: Show exactly what the model will receive for this character, including which sections did not fit the context budget. Loads nothing.
section: Reference
order: 200
parent: operations
revision: 1b13d3e2dc44ca9f
---

Show exactly what the model will receive for this character, including which sections did not fit the context budget. Loads nothing.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `persona` | `object` | No | See the operation parameters.  |
| `text` | `string` | No | See the operation parameters. `default=""` |
| `session_id` | `string` | No | See the operation parameters. `default=""` |
| `world_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `include_cast` | `boolean` | No | See the operation parameters. `default=true` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `messages` | `array` | No | See the operation parameters.  |
| `prompt` | `string` | No | See the operation parameters.  |
| `context` | `object` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preview_prompt
```
