---
id: operation-set-term-translations
title: set_term_translations
description: Set the rendering of terms in a language. A rendering set here is never replaced by the model; an empty text forgets it, so the next translation renders it again.
section: Reference
order: 200
parent: operations
revision: 50214c467a2575a1
---

Set the rendering of terms in a language. A rendering set here is never replaced by the model; an empty text forgets it, so the next translation renders it again.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `world_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `language` | `string` | Yes | See the operation parameters. `enum=["French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `terms` | `array` | Yes | See the operation parameters.  |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `worldId` | `string` | No | See the operation parameters.  |
| `language` | `string` | No | See the operation parameters.  |
| `changed` | `array` | No | See the operation parameters.  |
| `revision` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation set_term_translations
```
