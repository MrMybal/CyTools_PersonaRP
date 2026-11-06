---
id: operation-apply-proposal
title: apply_proposal
description: Intégrez une proposition dans un personnage ou un monde stocké. Seule la section cible est remplacée ; une nouvelle révision est écrite et la précédente est conservée.
section: Référence
order: 200
parent: operations
sourceRevision: d0ccf851122d5b5c
---

Intégrez une proposition dans un personnage ou un monde stocké. Seule la section cible est remplacée ; une nouvelle révision est écrite et la précédente est conservée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `world_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `target` | `string` | Non | Voir les paramètres de l’opération. `default="sheet"`, `enum=["appearance", "background", "canon", "dialogues", "factions", "glossary", "history", "identity", "locations", "media", "memory", "notes", "personality", "rules", "setting", "sheet", "speech", "state", "world"]` |
| `kind` | `string` | Non | Voir les paramètres de l’opération. `default="persona"`, `enum=["persona", "world"]` |
| `proposal` | `object/array/string` | Oui | Voir les paramètres de l’opération.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `document` | `object` | Non | Voir les paramètres de l’opération.  |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `revision` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation apply_proposal
```
