---
id: operation-get-assistant-thread
title: get_assistant_thread
description: Une discussion avec tous ses tournants.
section: Référence
order: 200
parent: operations
sourceRevision: 0af08781b5811c97
---

Une discussion avec tous ses tournants.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `thread_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `thread` | `object` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation get_assistant_thread
```
