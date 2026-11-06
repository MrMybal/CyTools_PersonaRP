---
id: operation-remove-persona
title: remove_persona
description: Déplacez une feuille et ses révisions dans data/personas/.trash. Rien n'est supprimé.
section: Référence
order: 200
parent: operations
sourceRevision: 2a18c624d0752f7a
---

Déplacez une feuille et ses révisions dans data/personas/.trash. Rien n'est supprimé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
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
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_persona
```
