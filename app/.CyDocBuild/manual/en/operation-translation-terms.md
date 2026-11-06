---
id: operation-translation-terms
title: translation_terms
description: The places, factions and glossary terms of a world, each with its rendering in a language, where it comes from (model or person) and which model rendered it.
section: Reference
order: 200
parent: operations
revision: ccfe1a3c9f477fb8
---

The places, factions and glossary terms of a world, each with its rendering in a language, where it comes from (model or person) and which model rendered it.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `world_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `language` | `string` | Yes | See the operation parameters. `enum=["French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `worldId` | `string` | No | See the operation parameters.  |
| `language` | `string` | No | See the operation parameters.  |
| `terms` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation translation_terms
```
