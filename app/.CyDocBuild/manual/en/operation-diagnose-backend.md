---
id: operation-diagnose-backend
title: diagnose_backend
description: Models, engines, devices, library counts and the storage layout actually in use.
section: Reference
order: 200
parent: operations
revision: 7bb074e52142e16c
---

Models, engines, devices, library counts and the storage layout actually in use.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `verify` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `models` | `array` | No | See the operation parameters.  |
| `engine` | `object` | No | See the operation parameters.  |
| `library` | `object` | No | See the operation parameters.  |
| `platform` | `string` | No | See the operation parameters.  |
| `resident` | `object` | No | See the operation parameters.  |
| `paths` | `object` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation diagnose_backend
```
