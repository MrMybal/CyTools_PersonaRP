---
id: operation-save-world
title: save_world
description: Write a new revision of a world.
section: Reference
order: 200
parent: operations
revision: 545cf4263092abb8
---

Write a new revision of a world.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `world` | `object` | Yes | See the operation parameters. `default={}` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `world` | `object` | No | See the operation parameters. `default={}` |
| `id` | `string` | No | See the operation parameters.  |
| `revision` | `integer` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_world
```
