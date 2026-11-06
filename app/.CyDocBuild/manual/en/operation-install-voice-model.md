---
id: operation-install-voice-model
title: install_voice_model
description: Download, resume or repair a speech model. The licence must be accepted personally.
section: Reference
order: 200
parent: operations
revision: 7f4a80c1354c8c89
---

Download, resume or repair a speech model. The licence must be accepted personally.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | See the operation parameters. `default=""` |
| `accept_license` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | No | See the operation parameters.  |
| `installed` | `boolean` | No | See the operation parameters.  |
| `sizeBytes` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_voice_model
```
