---
id: operation-list-voice-models
title: list_voice_models
description: Modèles de speech et leur état d’installation, taille, licence et source.
section: Référence
order: 200
parent: operations
sourceRevision: 3a6aaa863d450dbb
---

Modèles de speech et leur état d’installation, taille, licence et source.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `verify` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `models` | `array` | Non | Voir les paramètres de l’opération.  |
| `engine` | `object` | Non | Voir les paramètres de l’opération.  |
| `workers` | `object` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_voice_models
```
