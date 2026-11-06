---
id: operation-describe-image
title: describe_image
description: Lis une photographie de référence avec un modèle de vision et retourne la branche d'apparence : construction, visage, cheveux, yeux, peau, tenue, marques, accessoires et les tags visuels que chaque image ultérieure répète mot…
section: Référence
order: 200
parent: operations
sourceRevision: 88fa149c3fea60e1
---

Lis une photographie de référence avec un modèle de vision et retourne la branche d'apparence : construction, visage, cheveux, yeux, peau, tenue, marques, accessoires et les tags visuels que chaque image ultérieure répète mot pour mot. Deux passes : le modèle décrit d'abord la photo en prose libre (retournée sous forme d'observation, en anglais), puis écrit les champs à partir de cette observation dans la langue demandée, sous forme de phrases plutôt que de mots seuls. Le résultat est une proposition — applique-la avec apply_proposal.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `persona` | `object` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `image` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `use_existing` | `boolean` | Non | Il corrige ensuite plutôt que de commencer de zéro. `default=true` |
| `language` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `llm_model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "cpu", "cuda"]` |
| `keep_loaded` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `proposal` | `object` | Non | Voir les paramètres de l’opération.  |
| `text` | `string` | Non | Voir les paramètres de l’opération.  |
| `target` | `string` | Non | Voir les paramètres de l’opération.  |
| `kind` | `string` | Non | Voir les paramètres de l’opération.  |
| `model` | `string` | Non | Voir les paramètres de l’opération.  |
| `source` | `string` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `sentWidth` | `integer` | Non | Voir les paramètres de l’opération.  |
| `sentHeight` | `integer` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `observation` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation describe_image
```
