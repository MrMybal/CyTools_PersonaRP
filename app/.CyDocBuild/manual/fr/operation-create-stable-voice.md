---
id: operation-create-stable-voice
title: create_stable_voice
description: Enregistrez une prise d'audio comme une voix réutilisable. Chaque ligne ultérieure de ce personnage est clonée de cette prise, de sorte que la voix ne varie pas entre les réponses et entre les sessions. Les mots exacts de la…
section: Référence
order: 200
parent: operations
sourceRevision: f839e92040f1d03c
---

Enregistrez une prise d'audio comme une voix réutilisable. Chaque ligne ultérieure de ce personnage est clonée de cette prise, de sorte que la voix ne varie pas entre les réponses et entre les sessions. Les mots exacts de la prise sont nécessaires ; ils peuvent être transcrits ici.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `name` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `audio` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `transcript` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `attach` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `for_language` | `string` | Non | Empty en fait la voix principale du personnage. Une langue en fait la voix de cette langue seulement — la voix principale est conservée. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `model` | `string` | Non | Voir les paramètres de l’opération. `default="1.7B-Base"` |
| `language` | `string` | Non | Voir les paramètres de l’opération. `default="Auto"` |
| `description` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `source` | `string` | Non | Voir les paramètres de l’opération. `default="generated"`, `enum=["generated", "imported", "designed"]` |
| `transcribe` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default="cuda"`, `enum=["cuda", "cpu"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voice` | `object` | Non | Un récepteur vocal réutilisable construit à partir d’un court enregistrement de référence. `default={}` |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `attached` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `forLanguage` | `string` | Non | Voir les paramètres de l’opération.  |
| `warning` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation create_stable_voice
```
