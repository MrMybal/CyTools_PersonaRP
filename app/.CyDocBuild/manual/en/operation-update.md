---
id: operation-update
title: update
description: Check, stage, activate or roll back the application or the engine. Weights follow their own catalogue. data/ is never part of a replacement.
section: Reference
order: 200
parent: operations
revision: 1ea81d8f79d7096f
---

Check, stage, activate or roll back the application or the engine. Weights follow their own catalogue. data/ is never part of a replacement.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | No | See the operation parameters. `default="engine"`, `enum=["app", "engine"]` |
| `action` | `string` | No | See the operation parameters. `default="check"`, `enum=["check", "download", "activate", "rollback"]` |
| `repository` | `string` | No | Empty uses the repository this application ships with (release.json). `default=""` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `message` | `string` | No | See the operation parameters.  |
| `version` | `string` | No | See the operation parameters.  |
| `updateAvailable` | `boolean` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: `network`
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update
```
