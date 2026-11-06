---
id: operation-list-images
title: list_images
description: Chaque photographie de référence conservée par la bibliothèque, avec le personnage auquel elle appartient et si le fichier est toujours présent.
section: Référence
order: 200
parent: operations
sourceRevision: 254b1694de21122a
---

Chaque photographie de référence conservée par la bibliothèque, avec le personnage auquel elle appartient et si le fichier est toujours présent.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `images` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_images
```
