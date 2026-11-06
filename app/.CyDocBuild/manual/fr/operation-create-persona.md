---
id: operation-create-persona
title: create_persona
description: Créez une feuille à partir des champs fournis ; tout omis prend sa valeur par défaut.
section: Référence
order: 200
parent: operations
sourceRevision: 126da58a1cbcbc57
---

Créez une feuille à partir des champs fournis ; tout omis prend sa valeur par défaut.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération.  |
| `name` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation create_persona
```
