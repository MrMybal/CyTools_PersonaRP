---
id: operation-chat
title: chat
description: Generate an in-character reply. Returns the dialogue, the delivery annotations, and when the sheet asks for it a scene directive describing appearance, movement and camera for an image or video tool. The directive is data,…
section: Reference
order: 200
parent: operations
revision: d5c64b146fe10ad4
---

Generate an in-character reply. Returns the dialogue, the delivery annotations, and when the sheet asks for it a scene directive describing appearance, movement and camera for an image or video tool. The directive is data, never spoken.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `persona` | `object` | No | Used instead of persona_id when you do not want to store the character. One of the two is required.  |
| `text` | `string` | Yes | See the operation parameters. `default=""` |
| `session_id` | `string` | No | See the operation parameters. `default=""` |
| `history` | `array` | No | Only used when no session_id is given. `default=[]` |
| `world_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `include_cast` | `boolean` | No | See the operation parameters. `default=true` |
| `want_scene` | `string` | No | auto follows the character sheet. `default="auto"`, `enum=["auto", "yes", "no"]` |
| `speak` | `string` | No | See the operation parameters. `default="auto"`, `enum=["auto", "yes", "no"]` |
| `save` | `boolean` | No | See the operation parameters. `default=true` |
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
| `dialogue` | `string` | No | See the operation parameters.  |
| `spoken` | `string` | No | See the operation parameters.  |
| `scene` | `object` | No | See the operation parameters. `default={}` |
| `sceneError` | `string` | No | See the operation parameters.  |
| `rawScene` | `string` | No | See the operation parameters.  |
| `prompts` | `object` | No | See the operation parameters.  |
| `annotations` | `array` | No | See the operation parameters.  |
| `history` | `array` | No | See the operation parameters.  |
| `sessionId` | `string` | No | See the operation parameters.  |
| `audioFile` | `string` | No | See the operation parameters.  |
| `voiceError` | `string` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |
| `sessionFile` | `string` | No | See the operation parameters.  |
| `context` | `object` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `reused` | `boolean` | No | See the operation parameters.  |
| `mimeType` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation chat
```
