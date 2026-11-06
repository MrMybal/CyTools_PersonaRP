---
id: operation-create-persona
title: create_persona
description: Create a sheet from the supplied fields; everything omitted takes its default.
section: Reference
order: 200
parent: operations
revision: 126da58a1cbcbc57
---

Create a sheet from the supplied fields; everything omitted takes its default.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters.  |
| `name` | `string` | No | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters. `default={}` |
| `id` | `string` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation create_persona
```
