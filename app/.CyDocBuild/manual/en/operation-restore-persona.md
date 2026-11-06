---
id: operation-restore-persona
title: restore_persona
description: Bring back a past revision as a new revision, so nothing is lost either way.
section: Reference
order: 200
parent: operations
revision: c69d31d203f22285
---

Bring back a past revision as a new revision, so nothing is lost either way.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `revision` | `integer` | Yes | See the operation parameters. `minimum=0` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters. `default={}` |
| `revision` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation restore_persona
```
