---
id: operation-duplicate-persona
title: duplicate_persona
description: Copiez une feuille sous un nouvel identifiant.
section: Référence
order: 200
parent: operations
sourceRevision: cd1ad58f2b7a8d6a
---

Copiez une feuille sous un nouvel identifiant.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `name` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation duplicate_persona
```
