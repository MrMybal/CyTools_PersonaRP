---
id: operation-restore-persona
title: restore_persona
description: Ramener une révision passée en tant que nouvelle révision, de manière que rien ne soit perdu d'un côté ou de l'autre.
section: Référence
order: 200
parent: operations
sourceRevision: c69d31d203f22285
---

Ramener une révision passée en tant que nouvelle révision, de manière que rien ne soit perdu d'un côté ou de l'autre.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `revision` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `revision` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation restore_persona
```
