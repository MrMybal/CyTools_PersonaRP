---
id: operation-scene-prompts
title: scene_prompts
description: Transformez une directive en prompts d'image et de vidéo prêts à l'emploi, remplissant tout ce que le modèle a laissé vide du feuilleton du personnage et du monde. Rend nothing.
section: Référence
order: 200
parent: operations
sourceRevision: 2006757c0a6d7cbf
---

Transformez une directive en prompts d'image et de vidéo prêts à l'emploi, remplissant tout ce que le modèle a laissé vide du feuilleton du personnage et du monde. Rend nothing.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `scene` | `object` | Oui | Voir les paramètres de l’opération. `default={}` |
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `world_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `targets` | `array` | Non | Voir les paramètres de l’opération. `default=[]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `image_prompt` | `string` | Non | Voir les paramètres de l’opération.  |
| `video_prompt` | `string` | Non | Voir les paramètres de l’opération.  |
| `negative_prompt` | `string` | Non | Voir les paramètres de l’opération.  |
| `renderings` | `object` | Non | Voir les paramètres de l’opération.  |
| `summary` | `string` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation scene_prompts
```
