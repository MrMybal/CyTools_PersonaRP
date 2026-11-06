---
id: operation-list-voices
title: list_voices
description: Les voix dans la bibliothèque, avec leur enregistrement de référence.
section: Référence
order: 200
parent: operations
sourceRevision: 70053e10a9be324f
---

Les voix dans la bibliothèque, avec leur enregistrement de référence.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voices` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_voices
```
