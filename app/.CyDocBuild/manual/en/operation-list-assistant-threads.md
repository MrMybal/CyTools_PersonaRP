---
id: operation-list-assistant-threads
title: list_assistant_threads
description: Saved discussions, newest first.
section: Reference
order: 200
parent: operations
revision: 338a10d0be10e169
---

Saved discussions, newest first.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `threads` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_assistant_threads
```
