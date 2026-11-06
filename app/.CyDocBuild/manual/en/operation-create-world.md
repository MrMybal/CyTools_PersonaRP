---
id: operation-create-world
title: create_world
description: Create a shared lore document.
section: Reference
order: 200
parent: operations
revision: 78dbb073c1c7c823
---

Create a shared lore document.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `world` | `object` | No | See the operation parameters.  |
| `name` | `string` | No | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `world` | `object` | No | See the operation parameters. `default={}` |
| `id` | `string` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation create_world
```
