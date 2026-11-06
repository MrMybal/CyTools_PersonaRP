---
id: operation-capture-voice-take
title: capture_voice_take
description: Produisez la prise de référence d'une voix stable qui sert de base : environ 12 à 24 secondes d'audio, d'une description vocale écrite, d'un locuteur prédéfini ou de votre propre texte. Retourne la prise et son transcript pour…
section: Référence
order: 200
parent: operations
sourceRevision: dfb5d40063d2ab2f
---

Produisez la prise de référence d'une voix stable qui sert de base : environ 12 à 24 secondes d'audio, d'une description vocale écrite, d'un locuteur prédéfini ou de votre propre texte. Retourne la prise et son transcript pour qu'elle puisse être enregistrée immédiatement.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `description` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `speaker` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `text` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `language` | `string` | Non | Empty utilise la langue parlée du personnage. Sans texte donné, la prise par défaut est écrite dans cette langue. `default=""`, `enum=["", "Auto", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `seed` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `transcribe` | `boolean` | Non | Plus lent, mais il enregistre ce que le modèle a vraiment dit. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `workspaceFile` | `string` | Non | Voir les paramètres de l’opération.  |
| `transcript` | `string` | Non | Voir les paramètres de l’opération.  |
| `durationSeconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `inRange` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `advice` | `string` | Non | Voir les paramètres de l’opération.  |
| `mode` | `string` | Non | Voir les paramètres de l’opération.  |
| `model` | `string` | Non | Voir les paramètres de l’opération.  |
| `language` | `string` | Non | Voir les paramètres de l’opération.  |
| `mimeType` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation capture_voice_take
```
