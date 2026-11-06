---
id: operation-remember
title: remember
description: Apply facts, episodes and current state to a character. Memory is always explicit: nothing is harvested from a conversation without this call.
section: Reference
order: 200
parent: operations
revision: 6f9e0e8c49a3f52c
---

Apply facts, episodes and current state to a character. Memory is always explicit: nothing is harvested from a conversation without this call.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | Yes | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `facts` | `array` | No | See the operation parameters. `default=[]` |
| `episodes` | `array` | No | See the operation parameters. `default=[]` |
| `state` | `object` | No | What changes as the story advances.  |
| `replace_facts` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona` | `object` | No | See the operation parameters. `default={}` |
| `added` | `integer` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: not declared.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remember
```
