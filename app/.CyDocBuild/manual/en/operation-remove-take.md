---
id: operation-remove-take
title: remove_take
description: Move one take of a line to the trash beside the scene's takes (data/sessions/<character>/audio/<session>/.trash); nothing is deleted. When it was the take the line plays, the latest take left is played instead.
section: Reference
order: 200
parent: operations
revision: 2b91178e6326f676
---

Move one take of a line to the trash beside the scene's takes (data/sessions/<character>/audio/<session>/.trash); nothing is deleted. When it was the take the line plays, the latest take left is played instead.

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
| `trash` | `string` | No | See the operation parameters.  |
| `left` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_take
```
