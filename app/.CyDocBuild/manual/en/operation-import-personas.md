---
id: operation-import-personas
title: import_personas
description: Read a bundle, a single sheet or a single world. Existing identifiers are never overwritten: a clash produces a new identifier unless rename is off.
section: Reference
order: 200
parent: operations
revision: 2f018d05e4feba5c
---

Read a bundle, a single sheet or a single world. Existing identifiers are never overwritten: a clash produces a new identifier unless rename is off.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `file` | `string` | Yes | See the operation parameters. `default=""` |
| `rename` | `boolean` | No | See the operation parameters. `default=true` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `personas` | `array` | No | See the operation parameters.  |
| `worlds` | `array` | No | See the operation parameters.  |
| `voices` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation import_personas
```
