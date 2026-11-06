---
id: operation-add-persona-image
title: add_persona_image
description: Copy a reference photograph beside the sheet. It is kept with the character, travels with an export, and can be read by a vision model to fill the appearance. The roleplay model never sees it.
section: Reference
order: 200
parent: operations
revision: c40db1f93718dc7f
---

Copy a reference photograph beside the sheet. It is kept with the character, travels with an export, and can be read by a vision model to fill the appearance. The roleplay model never sees it.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `image` | `string` | Yes | See the operation parameters. `default=""` |
| `role` | `string` | No | See the operation parameters. `default="reference"`, `enum=["portrait", "full_body", "outfit", "detail", "expression", "setting", "reference"]` |
| `caption` | `string` | No | See the operation parameters. `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters. `default={}` |
| `references` | `array` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `filesystemExternal`
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation add_persona_image
```
