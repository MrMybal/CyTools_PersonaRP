---
id: operation-remove-voice
title: remove_voice
description: Déplacez une voix et son enregistrement dans data/voices/.trash. Rien n’est supprimé.
section: Référence
order: 200
parent: operations
sourceRevision: 0be57cbdce0b60ea
---

Déplacez une voix et son enregistrement dans data/voices/.trash. Rien n’est supprimé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voice_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `trash` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_voice
```
