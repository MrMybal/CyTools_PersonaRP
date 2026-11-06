---
id: operation-preview-prompt
title: preview_prompt
description: Affiche exactement ce que le modèle recevra pour ce personnage, y compris les sections qui n'ont pas correspondu au budget contextuel. Charge rien.
section: Référence
order: 200
parent: operations
sourceRevision: 1b13d3e2dc44ca9f
---

Affiche exactement ce que le modèle recevra pour ce personnage, y compris les sections qui n'ont pas correspondu au budget contextuel. Charge rien.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `persona` | `object` | Non | Voir les paramètres de l’opération.  |
| `text` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `session_id` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `world_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `include_cast` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `messages` | `array` | Non | Voir les paramètres de l’opération.  |
| `prompt` | `string` | Non | Voir les paramètres de l’opération.  |
| `context` | `object` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation preview_prompt
```
