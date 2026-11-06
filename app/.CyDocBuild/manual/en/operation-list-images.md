---
id: operation-list-images
title: list_images
description: Every reference photograph held by the library, with the character it belongs to and whether the file is still there.
section: Reference
order: 200
parent: operations
revision: 254b1694de21122a
---

Every reference photograph held by the library, with the character it belongs to and whether the file is still there.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `images` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_images
```
