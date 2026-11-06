---
id: operation-speak-turn
title: speak_turn
description: Lire l'une des lignes stockées d'un personnage, dans la langue du scénario ou l'une de ses traductions, avec la voix configurée par le feuille pour cette langue. La prise est conservée dans la session…
section: Référence
order: 200
parent: operations
sourceRevision: 86bc72ddbe251f4a
---

Lire l'une des lignes stockées d'un personnage, dans la langue du scénario ou l'une de ses traductions, avec la voix configurée par le feuille pour cette langue. La prise est conservée dans la session (data/sessions/<personnage>/audio/) et enregistrée au tour.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `turn` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `language` | `string` | Non | Empty parle dans la langue du personnage. Autre langue : elle utilise l'entrée correspondante dans voice.languages : la même voix avec ou sans son accent, une autre voix stable, une voix inventée ou un locuteur prédéfini. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `keep` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `seed` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `delivery` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "paragraphs", "segments", "complete"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `workspaceFile` | `string` | Non | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Non | Voir les paramètres de l’opération.  |
| `durationSeconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `sampleRate` | `integer` | Non | Voir les paramètres de l’opération.  |
| `turn` | `integer` | Non | Voir les paramètres de l’opération.  |
| `text` | `string` | Non | Voir les paramètres de l’opération.  |
| `language` | `string` | Non | Voir les paramètres de l’opération.  |
| `voicePlan` | `object` | Non | Voir les paramètres de l’opération.  |
| `mode` | `string` | Non | Voir les paramètres de l’opération.  |
| `model` | `string` | Non | Voir les paramètres de l’opération.  |
| `note` | `string` | Non | Voir les paramètres de l’opération.  |
| `generationSeconds` | `number` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak_turn
```
