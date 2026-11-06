---
id: operation-list-models
title: list_models
description: Catalogue with installation state, size, bytes present, licence and source.
section: Reference
order: 200
parent: operations
revision: 9a8fc7df742a9785
---

Catalogue with installation state, size, bytes present, licence and source.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `verify` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `models` | `array` | No | See the operation parameters.  |
| `engine` | `object` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_models
```
