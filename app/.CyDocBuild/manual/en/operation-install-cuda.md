---
id: operation-install-cuda
title: install_cuda
description: Download and verify the Windows x64 CUDA build of llama.cpp, then test it against the installed driver before recording it.
section: Reference
order: 200
parent: operations
revision: 1ae0ae83e4a57efb
---

Download and verify the Windows x64 CUDA build of llama.cpp, then test it against the installed driver before recording it.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `installed` | `boolean` | No | See the operation parameters.  |
| `version` | `string` | No | See the operation parameters.  |
| `devices` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_cuda
```
