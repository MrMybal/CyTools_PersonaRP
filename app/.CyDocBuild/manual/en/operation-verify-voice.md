---
id: operation-verify-voice
title: verify_voice
description: Check that the reference recording is still present and unchanged. A changed reference means the voice would no longer sound the same.
section: Reference
order: 200
parent: operations
revision: 558928e0586f90d1
---

Check that the reference recording is still present and unchanged. A changed reference means the voice would no longer sound the same.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `voice_id` | `string` | Yes | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | No | See the operation parameters.  |
| `ok` | `boolean` | No | See the operation parameters.  |
| `reason` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation verify_voice
```
