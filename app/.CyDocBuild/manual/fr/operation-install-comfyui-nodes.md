---
id: operation-install-comfyui-nodes
title: install_comfyui_nodes
description: Copiez les nœuds PersonaRP dans le dossier customnodes d'un ComfyUI (son dossier, son répertoire de base ou customnodes lui-même) avec un config.json qui nomme cet Outil. Les nœuds utilisent l'Outil via son local API — ils le…
section: Référence
order: 200
parent: operations
sourceRevision: d43b9aa3721d1412
---

Copiez les nœuds PersonaRP dans le dossier custom_nodes d'un ComfyUI (son dossier, son répertoire de base ou custom_nodes lui-même) avec un config.json qui nomme cet Outil. Les nœuds utilisent l'Outil via son local API — ils le lancent sur le port `port` quand il ne répond pas et que auto_start est activé — et ne l'importent jamais. Une nouvelle installation remplace la copie ; rien d'autre dans ComfyUI n'est touché. Redémarrez ComfyUI pour les charger.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `comfyui_path` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `port` | `integer` | Non | Voir les paramètres de l’opération. `default=8791`, `minimum=1024`, `maximum=65535` |
| `auto_start` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `folder` | `string` | Non | Voir les paramètres de l’opération.  |
| `files` | `integer` | Non | Voir les paramètres de l’opération.  |
| `packDigest` | `string` | Non | Voir les paramètres de l’opération.  |
| `toolRoot` | `string` | Non | Voir les paramètres de l’opération.  |
| `port` | `integer` | Non | Voir les paramètres de l’opération.  |
| `nodes` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_comfyui_nodes
```
