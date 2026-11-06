---
id: operation-remove-session
title: remove_session
description: Move a conversation to .trash next to the other sessions of that character.
section: Reference
order: 200
parent: operations
revision: 484d4bb8713e9e78
---

Move a conversation to .trash next to the other sessions of that character.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | Yes | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | No | See the operation parameters.  |
| `trash` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_session
```
