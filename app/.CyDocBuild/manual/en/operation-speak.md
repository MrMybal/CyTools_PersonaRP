---
id: operation-speak
title: speak
description: Render speech with a character's voice, or with an explicit voice. Delivery marks written in the text — [ton: …], [pause: 400ms], [emotion: …] — steer the take and are never pronounced.
section: Reference
order: 200
parent: operations
revision: 8f0c49d2528340f4
---

Render speech with a character's voice, or with an explicit voice. Delivery marks written in the text — [ton: …], [pause: 400ms], [emotion: …] — steer the take and are never pronounced.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `text` | `string` | Yes | See the operation parameters. `default=""` |
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `voice_id` | `string` | No | See the operation parameters. `default=""` |
| `voice` | `object` | No | Only the fields given here replace the character's own.  |
| `language` | `string` | No | Empty speaks in the character's own language. Another language uses the sheet's entry for it under voice.languages: the same voice with or without its accent, another stable voice, an invented voice or a preset speaker. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `model` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | See the operation parameters. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `seed` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `delivery` | `string` | No | See the operation parameters. `default=""`, `enum=["", "paragraphs", "segments", "complete"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | No | See the operation parameters.  |
| `mimeType` | `string` | No | See the operation parameters.  |
| `durationSeconds` | `number` | No | See the operation parameters.  |
| `sampleRate` | `integer` | No | See the operation parameters.  |
| `segments` | `array` | No | See the operation parameters.  |
| `chunks` | `array` | No | See the operation parameters.  |
| `mode` | `string` | No | See the operation parameters.  |
| `model` | `string` | No | See the operation parameters.  |
| `note` | `string` | No | See the operation parameters.  |
| `generationSeconds` | `number` | No | See the operation parameters.  |
| `language` | `string` | No | See the operation parameters.  |
| `voicePlan` | `object` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak
```
