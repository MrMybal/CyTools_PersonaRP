---
id: operation-get-world
title: get_world
description: The full world document and its cast.
section: Reference
order: 200
parent: operations
revision: 40242001883c6509
---

The full world document and its cast.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `world_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `world` | `object` | No | See the operation parameters. `default={}` |
| `cast` | `array` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation get_world
```
