---
id: operation-choose-take
title: choose_take
description: Every take of a line is kept (audio.takes, oldest first); audio itself describes the one the line plays. This chooses another one — take is its position in audio.takes, from 0.
section: Reference
order: 200
parent: operations
revision: a5f27835ea4de6e0
---

Every take of a line is kept (audio.takes, oldest first); audio itself describes the one the line plays. This chooses another one — take is its position in audio.takes, from 0.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | Yes | See the operation parameters. `default=""` |
| `turn` | `integer` | Yes | See the operation parameters. `minimum=0` |
| `language` | `string` | No | Empty speaks in the character's own language. Another language uses the sheet's entry for it under voice.languages: the same voice with or without its accent, another stable voice, an invented voice or a preset speaker. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `take` | `integer` | Yes | See the operation parameters. `minimum=0` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `audio` | `object/null` | No | See the operation parameters.  |
| `takes` | `array` | No | See the operation parameters.  |
| `chosen` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation choose_take
```
