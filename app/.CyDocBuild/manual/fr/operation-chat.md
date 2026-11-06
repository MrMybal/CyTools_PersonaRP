---
id: operation-chat
title: chat
description: Génère une réponse en caractère. Retourne le dialogue, les annotations de délivrance et, si la fiche le demande, une directive de scène décrivant l'apparence, le mouvement et la caméra pour un outil d'image ou de vidéo. La…
section: Référence
order: 200
parent: operations
sourceRevision: d5c64b146fe10ad4
---

Génère une réponse en caractère. Retourne le dialogue, les annotations de délivrance et, si la fiche le demande, une directive de scène décrivant l'apparence, le mouvement et la caméra pour un outil d'image ou de vidéo. La directive est des données, jamais prononcées.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `persona` | `object` | Non | Utilisé au lieu de persona_id lorsque vous ne souhaitez pas stocker le personnage. L'un des deux est requis.  |
| `text` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `session_id` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `history` | `array` | Non | Utilisé uniquement lorsque aucun session_id n'est fourni. `default=[]` |
| `world_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `include_cast` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `want_scene` | `string` | Non | auto suit la fiche du personnage. `default="auto"`, `enum=["auto", "yes", "no"]` |
| `speak` | `string` | Non | Voir les paramètres de l’opération. `default="auto"`, `enum=["auto", "yes", "no"]` |
| `save` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
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
| `text` | `string` | Non | Voir les paramètres de l’opération.  |
| `dialogue` | `string` | Non | Voir les paramètres de l’opération.  |
| `spoken` | `string` | Non | Voir les paramètres de l’opération.  |
| `scene` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `sceneError` | `string` | Non | Voir les paramètres de l’opération.  |
| `rawScene` | `string` | Non | Voir les paramètres de l’opération.  |
| `prompts` | `object` | Non | Voir les paramètres de l’opération.  |
| `annotations` | `array` | Non | Voir les paramètres de l’opération.  |
| `history` | `array` | Non | Voir les paramètres de l’opération.  |
| `sessionId` | `string` | Non | Voir les paramètres de l’opération.  |
| `audioFile` | `string` | Non | Voir les paramètres de l’opération.  |
| `voiceError` | `string` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `sessionFile` | `string` | Non | Voir les paramètres de l’opération.  |
| `context` | `object` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `reused` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation chat
```
