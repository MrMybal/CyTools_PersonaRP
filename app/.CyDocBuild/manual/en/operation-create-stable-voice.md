---
id: operation-create-stable-voice
title: create_stable_voice
description: Register a recording as a reusable voice. Every later line of that character is cloned from this take, so the voice stops drifting between replies and between sessions. The exact words of the take are required; they can be…
section: Reference
order: 200
parent: operations
revision: f839e92040f1d03c
---

Register a recording as a reusable voice. Every later line of that character is cloned from this take, so the voice stops drifting between replies and between sessions. The exact words of the take are required; they can be transcribed here.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | Yes | See the operation parameters. `default=""` |
| `audio` | `string` | Yes | See the operation parameters. `default=""` |
| `transcript` | `string` | No | See the operation parameters. `default=""` |
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `attach` | `boolean` | No | See the operation parameters. `default=true` |
| `for_language` | `string` | No | Empty makes it the character's main voice. A language makes it the voice of that language only — the main voice is kept. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `model` | `string` | No | See the operation parameters. `default="1.7B-Base"` |
| `language` | `string` | No | See the operation parameters. `default="Auto"` |
| `description` | `string` | No | See the operation parameters. `default=""` |
| `source` | `string` | No | See the operation parameters. `default="generated"`, `enum=["generated", "imported", "designed"]` |
| `transcribe` | `boolean` | No | See the operation parameters. `default=false` |
| `device` | `string` | No | See the operation parameters. `default="cuda"`, `enum=["cuda", "cpu"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `voice` | `object` | No | A reusable voice built from a short reference take. `default={}` |
| `id` | `string` | No | See the operation parameters.  |
| `attached` | `boolean` | No | See the operation parameters.  |
| `forLanguage` | `string` | No | See the operation parameters.  |
| `warning` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation create_stable_voice
```
