---
id: operation-list-batches
title: list_batches
description: Every batch folder in data/batches, newest first, with how many of its lines are done.
section: Reference
order: 200
parent: operations
revision: 2c46c688caf11118
---

Every batch folder in data/batches, newest first, with how many of its lines are done.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `folder` | `string` | No | See the operation parameters.  |
| `batches` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_batches
```
