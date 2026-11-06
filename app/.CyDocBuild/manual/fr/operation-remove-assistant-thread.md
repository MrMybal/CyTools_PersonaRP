---
id: operation-remove-assistant-thread
title: remove_assistant_thread
description: Déplace une discussion vers data/assistant/.trash. Rien n'est supprimé.
section: Référence
order: 200
parent: operations
sourceRevision: 113e2fccfab0574f
---

Déplace une discussion vers data/assistant/.trash. Rien n'est supprimé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `thread_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `trash` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_assistant_thread
```
