---
id: operation-capture-voice-take
title: capture_voice_take
description: Produce the reference recording a stable voice is built from: roughly 12 to 24 seconds of speech, from a written voice description, from a preset speaker, or from your own text. Returns the take and its transcript so it can be…
section: Reference
order: 200
parent: operations
revision: dfb5d40063d2ab2f
---

Produce the reference recording a stable voice is built from: roughly 12 to 24 seconds of speech, from a written voice description, from a preset speaker, or from your own text. Returns the take and its transcript so it can be registered straight away.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `description` | `string` | No | See the operation parameters. `default=""` |
| `speaker` | `string` | No | See the operation parameters. `default=""` |
| `text` | `string` | No | See the operation parameters. `default=""` |
| `model` | `string` | No | See the operation parameters. `default=""` |
| `language` | `string` | No | Empty uses the character's spoken language. With no text given, the default take is written in this language. `default=""`, `enum=["", "Auto", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `device` | `string` | No | See the operation parameters. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `seed` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `transcribe` | `boolean` | No | Slower, but it records what the model really said. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | No | See the operation parameters.  |
| `workspaceFile` | `string` | No | See the operation parameters.  |
| `transcript` | `string` | No | See the operation parameters.  |
| `durationSeconds` | `number` | No | See the operation parameters.  |
| `inRange` | `boolean` | No | See the operation parameters.  |
| `advice` | `string` | No | See the operation parameters.  |
| `mode` | `string` | No | See the operation parameters.  |
| `model` | `string` | No | See the operation parameters.  |
| `language` | `string` | No | See the operation parameters.  |
| `mimeType` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation capture_voice_take
```
