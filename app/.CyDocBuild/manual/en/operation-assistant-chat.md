---
id: operation-assistant-chat
title: assistant_chat
description: One turn of free discussion, with no character and no scene. The thread is written to disk before the reply comes back, so nothing has to be saved by hand. Several threads can be open at once.
section: Reference
order: 200
parent: operations
revision: 5098492ee1b66dfa
---

One turn of free discussion, with no character and no scene. The thread is written to disk before the reply comes back, so nothing has to be saved by hand. Several threads can be open at once.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `string` | No | See the operation parameters. `default=""` |
| `text` | `string` | Yes | See the operation parameters. `default=""` |
| `image` | `string` | No | See the operation parameters. `default=""` |
| `vision_model` | `string` | No | See the operation parameters. `default=""` |
| `title` | `string` | No | See the operation parameters. `default=""` |
| `system` | `string` | No | See the operation parameters. `default=""` |
| `context_budget` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=1024`, `maximum=60000` |
| `llm_model` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | Empty keeps the device recorded on the character sheet. `default=""`, `enum=["", "cpu", "cuda"]` |
| `temperature` | `number/null` | No | See the operation parameters. `default=null`, `minimum=0`, `maximum=2` |
| `response_length` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=16`, `maximum=4096` |
| `seed` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `threads` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=1`, `maximum=64` |
| `keep_loaded` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `text` | `string` | No | See the operation parameters.  |
| `threadId` | `string` | No | See the operation parameters.  |
| `title` | `string` | No | See the operation parameters.  |
| `turns` | `array` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `reused` | `boolean` | No | See the operation parameters.  |
| `truncated` | `boolean` | No | See the operation parameters.  |
| `picture` | `object` | No | See the operation parameters.  |
| `context` | `object` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |
| `mimeType` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation assistant_chat
```
