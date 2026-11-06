---
id: operation-list-personas
title: list_personas
description: Every stored character, newest change first.
section: Reference
order: 200
parent: operations
revision: 26ea6b9fc963210a
---

Every stored character, newest change first.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `world_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `personas` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_personas
```
