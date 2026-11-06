---
id: operation-author
title: author
description: Écrivez un feuille de personnage, un monde, ou une section de l'un ou l'autre. L'assistant ne joue jamais le personnage et ne écrit jamais à la bibliothèque ; applyproposal le fait explicitement.
section: Référence
order: 200
parent: operations
sourceRevision: 221e0c7f2140cc9d
---

Écrivez un feuille de personnage, un monde, ou une section de l'un ou l'autre. L'assistant ne joue jamais le personnage et ne écrit jamais à la bibliothèque ; apply_proposal le fait explicitement.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `request` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `target` | `string` | Non | Voir les paramètres de l’opération. `default="sheet"`, `enum=["appearance", "background", "canon", "dialogues", "factions", "glossary", "history", "identity", "locations", "media", "memory", "notes", "personality", "rules", "setting", "sheet", "speech", "state", "world"]` |
| `kind` | `string` | Non | Voir les paramètres de l’opération. `default="persona"`, `enum=["persona", "world"]` |
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `world_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `thread_id` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `image` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `vision_model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `language` | `string` | Non | Voir les paramètres de l’opération. `default="Francais"` |
| `llm_model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `device` | `string` | Non | Vide conserve le périphérique enregistré sur la fiche du personnage. `default=""`, `enum=["", "cpu", "cuda"]` |
| `temperature` | `number/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=0`, `maximum=2` |
| `response_length` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=16`, `maximum=4096` |
| `seed` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `threads` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=1`, `maximum=64` |
| `keep_loaded` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `proposal` | `object/array/string` | Non | Voir les paramètres de l’opération.  |
| `raw` | `string` | Non | Voir les paramètres de l’opération.  |
| `target` | `string` | Non | Voir les paramètres de l’opération.  |
| `kind` | `string` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `picture` | `object` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation author
```
