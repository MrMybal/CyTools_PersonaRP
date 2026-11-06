---
id: operation-get-world
title: get_world
description: Le monde entier documenté et son casting.
section: Référence
order: 200
parent: operations
sourceRevision: 40242001883c6509
---

Le monde entier documenté et son casting.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `cast` | `array` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation get_world
```
