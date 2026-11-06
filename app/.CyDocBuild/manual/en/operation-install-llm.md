---
id: operation-install-llm
title: install_llm
description: Download, resume or repair the weights of one catalogue model. The licence must be accepted personally first.
section: Reference
order: 200
parent: operations
revision: a1354fa71337710f
---

Download, resume or repair the weights of one catalogue model. The licence must be accepted personally first.

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
runtime\python\Scripts\python.exe app\tool.py describe-operation install_llm
```
