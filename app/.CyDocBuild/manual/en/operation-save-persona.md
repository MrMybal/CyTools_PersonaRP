---
id: operation-save-persona
title: save_persona
description: Write a new revision of an existing sheet. The previous revision is kept.
section: Reference
order: 200
parent: operations
revision: 7b482e1a0b1ee59a
---

Write a new revision of an existing sheet. The previous revision is kept.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | Yes | See the operation parameters. `default={}` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters. `default={}` |
| `id` | `string` | No | See the operation parameters.  |
| `revision` | `integer` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_persona
```
