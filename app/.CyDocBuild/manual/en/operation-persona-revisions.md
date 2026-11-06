---
id: operation-persona-revisions
title: persona_revisions
description: Past revisions kept next to a sheet.
section: Reference
order: 200
parent: operations
revision: 2d271cbfcbe8ea09
---

Past revisions kept next to a sheet.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `revisions` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation persona_revisions
```
