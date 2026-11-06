---
id: operation-list-examples
title: list_examples
description: The example worlds shipped with the Tool — epic fantasy, science fiction, cyberpunk, gothic horror, post-apocalypse, gentle fantasy — each a bundle of a world and its cast. Import one with importpersonas and the file given…
section: Reference
order: 200
parent: operations
revision: 8c5092a2c2c4c699
---

The example worlds shipped with the Tool — epic fantasy, science fiction, cyberpunk, gothic horror, post-apocalypse, gentle fantasy — each a bundle of a world and its cast. Import one with import_personas and the file given here; an import is a copy, and an existing identifier is never overwritten.

## Parameters {#contract}

No named fields are declared at this level. Inspect the operation schema with `describe-operation` for its exact shape.
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `examples` | `array` | No | See the operation parameters.  |
| `folder` | `string` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_examples
```
