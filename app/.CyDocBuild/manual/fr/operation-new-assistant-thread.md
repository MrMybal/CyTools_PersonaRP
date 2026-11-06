---
id: operation-new-assistant-thread
title: new_assistant_thread
description: Démarrez un fil de discussion vide.
section: Référence
order: 200
parent: operations
sourceRevision: b3b23fa5f3a2907c
---

Démarrez un fil de discussion vide.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `title` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `system` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `thread` | `object` | Non | Voir les paramètres de l’opération.  |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation new_assistant_thread
```
