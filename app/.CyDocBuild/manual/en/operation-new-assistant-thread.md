---
id: operation-new-assistant-thread
title: new_assistant_thread
description: Start an empty discussion thread.
section: Reference
order: 200
parent: operations
revision: b3b23fa5f3a2907c
---

Start an empty discussion thread.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `title` | `string` | No | See the operation parameters. `default=""` |
| `system` | `string` | No | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `thread` | `object` | No | See the operation parameters.  |
| `id` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation new_assistant_thread
```
