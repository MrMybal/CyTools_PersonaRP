---
id: operation-save-assistant-thread
title: save_assistant_thread
description: Keep the title, the standing instruction, the unsent draft and the model settings of a discussion without sending anything.
section: Reference
order: 200
parent: operations
revision: 3bfa2c0aa525b775
---

Keep the title, the standing instruction, the unsent draft and the model settings of a discussion without sending anything.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `string` | Yes | See the operation parameters. `default=""` |
| `title` | `string` | No | See the operation parameters. `default=""` |
| `system` | `string` | No | See the operation parameters. `default=""` |
| `draft` | `string` | No | See the operation parameters. `default=""` |
| `llm_model` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | See the operation parameters. `default=""`, `enum=["", "cpu", "cuda"]` |
| `temperature` | `number/null` | No | See the operation parameters. `default=null`, `minimum=0`, `maximum=2` |
| `response_length` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=16`, `maximum=4096` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `thread` | `object` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_assistant_thread
```
