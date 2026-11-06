---
id: operation-remove-assistant-thread
title: remove_assistant_thread
description: Move a discussion to data/assistant/.trash. Nothing is deleted.
section: Reference
order: 200
parent: operations
revision: 113e2fccfab0574f
---

Move a discussion to data/assistant/.trash. Nothing is deleted.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `string` | Yes | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | No | See the operation parameters.  |
| `trash` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_assistant_thread
```
