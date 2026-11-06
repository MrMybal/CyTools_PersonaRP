---
id: operation-install-voice-model
title: install_voice_model
description: Téléchargez, reprenez ou réparez un modèle de speech. La licence doit être acceptée personnellement.
section: Référence
order: 200
parent: operations
sourceRevision: 7f4a80c1354c8c89
---

Téléchargez, reprenez ou réparez un modèle de speech. La licence doit être acceptée personnellement.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `accept_license` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Non | Voir les paramètres de l’opération.  |
| `installed` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `sizeBytes` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_voice_model
```
