---
id: operation-save-world
title: save_world
description: Écrire une nouvelle révision d'un monde.
section: Référence
order: 200
parent: operations
sourceRevision: 545cf4263092abb8
---

Écrire une nouvelle révision d'un monde.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world` | `object` | Oui | Voir les paramètres de l’opération. `default={}` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `revision` | `integer` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_world
```
