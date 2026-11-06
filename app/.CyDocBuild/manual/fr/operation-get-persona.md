---
id: operation-get-persona
title: get_persona
description: La feuille complète telle qu'elle est stockée.
section: Référence
order: 200
parent: operations
sourceRevision: ca09e27e3556c200
---

La feuille complète telle qu'elle est stockée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `world` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation get_persona
```
