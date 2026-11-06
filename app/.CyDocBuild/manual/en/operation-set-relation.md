---
id: operation-set-relation
title: set_relation
description: Create or update how one character feels about another, optionally writing the mirror bond on the other sheet as well.
section: Reference
order: 200
parent: operations
revision: 3b27332bedcd50b6
---

Create or update how one character feels about another, optionally writing the mirror bond on the other sheet as well.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `relation` | `object` | Yes | See the operation parameters. `default={}` |
| `reciprocal` | `object` | No | Written on the other sheet when supplied.  |
| `mirror` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters. `default={}` |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation set_relation
```
