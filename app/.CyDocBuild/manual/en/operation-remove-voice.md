---
id: operation-remove-voice
title: remove_voice
description: Move a voice and its recording to data/voices/.trash. Nothing is deleted.
section: Reference
order: 200
parent: operations
revision: 0be57cbdce0b60ea
---

Move a voice and its recording to data/voices/.trash. Nothing is deleted.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `voice_id` | `string` | Yes | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | No | See the operation parameters.  |
| `trash` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_voice
```
