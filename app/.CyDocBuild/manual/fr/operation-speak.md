---
id: operation-speak
title: speak
description: Render l'audio avec la voix d'un personnage ou avec une voix explicite. Les marques de livraison écrites dans le texte — [ton: …], [pause: 400ms], [émotion: …] — dirigent la prise et ne sont jamais prononcées.
section: Référence
order: 200
parent: operations
sourceRevision: 8f0c49d2528340f4
---

Render l'audio avec la voix d'un personnage ou avec une voix explicite. Les marques de livraison écrites dans le texte — [ton: …], [pause: 400ms], [émotion: …] — dirigent la prise et ne sont jamais prononcées.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `text` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `voice_id` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `voice` | `object` | Non | Seules les champs donnés ici remplacent la voix du personnage.  |
| `language` | `string` | Non | Empty parle dans la langue du personnage. Autre langue : elle utilise l'entrée correspondante dans voice.languages : la même voix avec ou sans son accent, une autre voix stable, une voix inventée ou un locuteur prédéfini. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `seed` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `delivery` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "paragraphs", "segments", "complete"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Non | Voir les paramètres de l’opération.  |
| `durationSeconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `sampleRate` | `integer` | Non | Voir les paramètres de l’opération.  |
| `segments` | `array` | Non | Voir les paramètres de l’opération.  |
| `chunks` | `array` | Non | Voir les paramètres de l’opération.  |
| `mode` | `string` | Non | Voir les paramètres de l’opération.  |
| `model` | `string` | Non | Voir les paramètres de l’opération.  |
| `note` | `string` | Non | Voir les paramètres de l’opération.  |
| `generationSeconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `language` | `string` | Non | Voir les paramètres de l’opération.  |
| `voicePlan` | `object` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak
```
