---
id: operation-remove-world
title: remove_world
description: Move a world to data/worlds/.trash. Characters keep their worldid.
section: Reference
order: 200
parent: operations
revision: 05616d8044e9045f
---

Move a world to data/worlds/.trash. Characters keep their world_id.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `world_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
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
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_world
```
