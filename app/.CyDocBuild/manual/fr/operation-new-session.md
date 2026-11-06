---
id: operation-new-session
title: new_session
description: Ouvrir une conversation fraîche pour un personnage.
section: Référence
order: 200
parent: operations
sourceRevision: 3806fc2bea627f0d
---

Ouvrir une conversation fraîche pour un personnage.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `title` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `session` | `object` | Non | Voir les paramètres de l’opération.  |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation new_session
```
