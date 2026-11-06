---
id: operation-add-persona-image
title: add_persona_image
description: Copie une photographie de référence à côté du feuillet. Elle est conservée avec le personnage, voyage avec un export et peut être lue par un modèle de vision pour remplir l'apparence. Le modèle de jeu ne la voit jamais.
section: Référence
order: 200
parent: operations
sourceRevision: c40db1f93718dc7f
---

Copie une photographie de référence à côté du feuillet. Elle est conservée avec le personnage, voyage avec un export et peut être lue par un modèle de vision pour remplir l'apparence. Le modèle de jeu ne la voit jamais.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `image` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `role` | `string` | Non | Voir les paramètres de l’opération. `default="reference"`, `enum=["portrait", "full_body", "outfit", "detail", "expression", "setting", "reference"]` |
| `caption` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `references` | `array` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation add_persona_image
```
