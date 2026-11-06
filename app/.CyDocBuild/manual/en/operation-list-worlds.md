---
id: operation-list-worlds
title: list_worlds
description: Every stored world.
section: Reference
order: 200
parent: operations
revision: 2f424501e615f6c5
---

Every stored world.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `worlds` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_worlds
```
