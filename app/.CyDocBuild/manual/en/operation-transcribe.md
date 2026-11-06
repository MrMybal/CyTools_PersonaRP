---
id: operation-transcribe
title: transcribe
description: Speech to text with Whisper, for a reference take or for dictating a message.
section: Reference
order: 200
parent: operations
revision: 976d5c4a6d7bb625
---

Speech to text with Whisper, for a reference take or for dictating a message.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `audio` | `string` | Yes | See the operation parameters. `default=""` |
| `language` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | See the operation parameters. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `timestamps` | `boolean` | No | See the operation parameters. `default=true` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `text` | `string` | No | See the operation parameters.  |
| `segments` | `array` | No | See the operation parameters.  |
| `durationSeconds` | `number` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation transcribe
```
