---
id: operation-list-voice-models
title: list_voice_models
description: Speech models and their installation state, size, licence and source.
section: Reference
order: 200
parent: operations
revision: 3a6aaa863d450dbb
---

Speech models and their installation state, size, licence and source.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `verify` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `models` | `array` | No | See the operation parameters.  |
| `engine` | `object` | No | See the operation parameters.  |
| `workers` | `object` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_voice_models
```
