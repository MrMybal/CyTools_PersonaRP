---
id: operation-save-persona
title: save_persona
description: Écrivez une nouvelle révision d'une feuille existante. La révision précédente est conservée.
section: Référence
order: 200
parent: operations
sourceRevision: 7b482e1a0b1ee59a
---

Écrivez une nouvelle révision d'une feuille existante. La révision précédente est conservée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Oui | Voir les paramètres de l’opération. `default={}` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `revision` | `integer` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_persona
```
