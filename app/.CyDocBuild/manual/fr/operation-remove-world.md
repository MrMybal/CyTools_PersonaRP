---
id: operation-remove-world
title: remove_world
description: Déplacer un monde vers data/worlds/.trash. Les personnages conservent leur worldid.
section: Référence
order: 200
parent: operations
sourceRevision: 05616d8044e9045f
---

Déplacer un monde vers data/worlds/.trash. Les personnages conservent leur world_id.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
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
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_world
```
