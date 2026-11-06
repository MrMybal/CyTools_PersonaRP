---
id: operation-transcribe
title: transcribe
description: Speech to text avec Whisper, pour un enregistrement de référence ou pour dictater un message.
section: Référence
order: 200
parent: operations
sourceRevision: 976d5c4a6d7bb625
---

Speech to text avec Whisper, pour un enregistrement de référence ou pour dictater un message.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `audio` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `language` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `timestamps` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `text` | `string` | Non | Voir les paramètres de l’opération.  |
| `segments` | `array` | Non | Voir les paramètres de l’opération.  |
| `durationSeconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation transcribe
```
