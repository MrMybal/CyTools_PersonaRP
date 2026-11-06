---
id: operation-install-voice-engine
title: install_voice_engine
description: Create or repair the private speech environment (PyTorch, Qwen3-TTS, Whisper) at its final path, then import-check it. Nothing is recorded as installed before that passes.
section: Reference
order: 200
parent: operations
revision: 7d294caa8236cfdc
---

Create or repair the private speech environment (PyTorch, Qwen3-TTS, Whisper) at its final path, then import-check it. Nothing is recorded as installed before that passes.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `cpu_only` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `installed` | `boolean` | No | See the operation parameters.  |
| `log` | `string` | No | See the operation parameters.  |
| `report` | `object` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_voice_engine
```
