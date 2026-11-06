---
id: operation-release-voice
title: release_voice
description: Stop the speech processes and free their RAM and VRAM.
section: Reference
order: 200
parent: operations
revision: 95d261f857e43940
---

Stop the speech processes and free their RAM and VRAM.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `released` | `boolean` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation release_voice
```
