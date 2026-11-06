---
id: operation-verify-persona-images
title: verify_persona_images
description: Check that every photograph of a sheet is still present and unchanged.
section: Reference
order: 200
parent: operations
revision: 24aa64013713f4ba
---

Check that every photograph of a sheet is still present and unchanged.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `references` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation verify_persona_images
```
