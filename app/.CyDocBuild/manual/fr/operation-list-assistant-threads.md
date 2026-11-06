---
id: operation-list-assistant-threads
title: list_assistant_threads
description: Les discussions enregistrées, le plus récent en premier.
section: Référence
order: 200
parent: operations
sourceRevision: 338a10d0be10e169
---

Les discussions enregistrées, le plus récent en premier.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `threads` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_assistant_threads
```
