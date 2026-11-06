---
id: operation-get-assistant-thread
title: get_assistant_thread
description: A discussion with all of its turns.
section: Reference
order: 200
parent: operations
revision: 0af08781b5811c97
---

A discussion with all of its turns.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `string` | Yes | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `thread` | `object` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation get_assistant_thread
```
