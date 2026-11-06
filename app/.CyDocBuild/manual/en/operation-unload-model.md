---
id: operation-unload-model
title: unload_model
description: Stop the conversation server and release its RAM and VRAM reservation.
section: Reference
order: 200
parent: operations
revision: 42ddaa33672068f5
---

Stop the conversation server and release its RAM and VRAM reservation.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `loaded` | `boolean` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation unload_model
```
