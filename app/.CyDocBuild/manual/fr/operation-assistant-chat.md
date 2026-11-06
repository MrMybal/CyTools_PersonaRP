---
id: operation-assistant-chat
title: assistant_chat
description: Une tour de discussion libre, sans personnage et sans scène. Le fil est écrit sur le disque avant que la réponse ne revienne, de sorte qu'il n'y a rien à sauvegarder à la main. Plusieurs fils peuvent être ouverts en même temps.
section: Référence
order: 200
parent: operations
sourceRevision: 5098492ee1b66dfa
---

Une tour de discussion libre, sans personnage et sans scène. Le fil est écrit sur le disque avant que la réponse ne revienne, de sorte qu'il n'y a rien à sauvegarder à la main. Plusieurs fils peuvent être ouverts en même temps.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `thread_id` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `text` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `image` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `vision_model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `title` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `system` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `context_budget` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=1024`, `maximum=60000` |
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
| `threadId` | `string` | Non | Voir les paramètres de l’opération.  |
| `title` | `string` | Non | Voir les paramètres de l’opération.  |
| `turns` | `array` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `reused` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `truncated` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `picture` | `object` | Non | Voir les paramètres de l’opération.  |
| `context` | `object` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation assistant_chat
```
