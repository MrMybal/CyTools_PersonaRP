---
id: operation-persona-revisions
title: persona_revisions
description: Les révisions précédentes sont conservées à côté d'un feuille.
section: Référence
order: 200
parent: operations
sourceRevision: 2d271cbfcbe8ea09
---

Les révisions précédentes sont conservées à côté d'un feuille.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `revisions` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation persona_revisions
```
