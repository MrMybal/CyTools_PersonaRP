---
id: operation-get-session
title: get_session
description: A saved conversation with its scene directives.
section: Reference
order: 200
parent: operations
revision: 9a60a9959549bf2d
---

A saved conversation with its scene directives.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | Yes | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `session` | `object` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation get_session
```
