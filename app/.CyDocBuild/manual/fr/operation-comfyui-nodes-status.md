---
id: operation-comfyui-nodes-status
title: comfyui_nodes_status
description: Les installations ComfyUI trouvées sur cette machine (Comfy Desktop), plus comfyuipath si fourni, chacune avec la présence et la mise à jour des nœuds PersonaRP.
section: Référence
order: 200
parent: operations
sourceRevision: c2ed67316642a871
---

Les installations ComfyUI trouvées sur cette machine (Comfy Desktop), plus comfyui_path si fourni, chacune avec la présence et la mise à jour des nœuds PersonaRP.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `comfyui_path` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `comfyui` | `array` | Non | Voir les paramètres de l’opération.  |
| `nodes` | `array` | Non | Voir les paramètres de l’opération.  |
| `packDigest` | `string` | Non | Voir les paramètres de l’opération.  |
| `toolRoot` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation comfyui_nodes_status
```
