---
id: operation-speak-turn
title: speak_turn
description: Speak one of the character's stored lines, in the scene's own language or in one of its translations, with the voice the sheet configures for that language. The take is kept with the session (data/sessions/<character>/audio/)…
section: Reference
order: 200
parent: operations
revision: 86bc72ddbe251f4a
---

Speak one of the character's stored lines, in the scene's own language or in one of its translations, with the voice the sheet configures for that language. The take is kept with the session (data/sessions/<character>/audio/) and recorded on the turn.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | Yes | See the operation parameters. `default=""` |
| `turn` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `language` | `string` | No | Empty speaks in the character's own language. Another language uses the sheet's entry for it under voice.languages: the same voice with or without its accent, another stable voice, an invented voice or a preset speaker. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `keep` | `boolean` | No | See the operation parameters. `default=true` |
| `model` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | See the operation parameters. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `seed` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `delivery` | `string` | No | See the operation parameters. `default=""`, `enum=["", "paragraphs", "segments", "complete"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | No | See the operation parameters.  |
| `workspaceFile` | `string` | No | See the operation parameters.  |
| `mimeType` | `string` | No | See the operation parameters.  |
| `durationSeconds` | `number` | No | See the operation parameters.  |
| `sampleRate` | `integer` | No | See the operation parameters.  |
| `turn` | `integer` | No | See the operation parameters.  |
| `text` | `string` | No | See the operation parameters.  |
| `language` | `string` | No | See the operation parameters.  |
| `voicePlan` | `object` | No | See the operation parameters.  |
| `mode` | `string` | No | See the operation parameters.  |
| `model` | `string` | No | See the operation parameters.  |
| `note` | `string` | No | See the operation parameters.  |
| `generationSeconds` | `number` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak_turn
```
