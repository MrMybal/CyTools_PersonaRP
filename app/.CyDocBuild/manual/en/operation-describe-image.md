---
id: operation-describe-image
title: describe_image
description: Read a reference photograph with a vision model and return the appearance branch: build, face, hair, eyes, skin, outfit, marks, accessories, and the visual tags that every later image prompt repeats word for word. Two passes:…
section: Reference
order: 200
parent: operations
revision: 88fa149c3fea60e1
---

Read a reference photograph with a vision model and return the appearance branch: build, face, hair, eyes, skin, outfit, marks, accessories, and the visual tags that every later image prompt repeats word for word. Two passes: the model first describes the picture in free prose (returned as observation, in English), then writes the fields from that observation in the language asked, as phrases rather than single words. The result is a proposal — apply it with apply_proposal.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `persona` | `object` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters. `default=""` |
| `image` | `string` | No | See the operation parameters. `default=""` |
| `use_existing` | `boolean` | No | It then corrects rather than starting from nothing. `default=true` |
| `language` | `string` | No | See the operation parameters. `default=""` |
| `llm_model` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | See the operation parameters. `default=""`, `enum=["", "cpu", "cuda"]` |
| `keep_loaded` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `proposal` | `object` | No | See the operation parameters.  |
| `text` | `string` | No | See the operation parameters.  |
| `target` | `string` | No | See the operation parameters.  |
| `kind` | `string` | No | See the operation parameters.  |
| `model` | `string` | No | See the operation parameters.  |
| `source` | `string` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `sentWidth` | `integer` | No | See the operation parameters.  |
| `sentHeight` | `integer` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |
| `observation` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation describe_image
```
