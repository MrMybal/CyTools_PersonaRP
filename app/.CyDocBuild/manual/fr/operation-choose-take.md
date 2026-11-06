---
id: operation-choose-take
title: choose_take
description: Chaque prise d'une ligne est conservée (audio.takes, la plus ancienne en premier) ; l'enregistrement audio lui-même décrit celle qui est jouée. Cela choisit une autre — take est sa position dans audio.takes, de 0.
section: Référence
order: 200
parent: operations
sourceRevision: a5f27835ea4de6e0
---

Chaque prise d'une ligne est conservée (audio.takes, la plus ancienne en premier) ; l'enregistrement audio lui-même décrit celle qui est jouée. Cela choisit une autre — take est sa position dans audio.takes, de 0.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `turn` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
| `language` | `string` | Non | Empty parle dans la langue du personnage. Autre langue : elle utilise l'entrée correspondante dans voice.languages : la même voix avec ou sans son accent, une autre voix stable, une voix inventée ou un locuteur prédéfini. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `take` | `integer` | Oui | Voir les paramètres de l’opération. `minimum=0` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `audio` | `object/null` | Non | Voir les paramètres de l’opération.  |
| `takes` | `array` | Non | Voir les paramètres de l’opération.  |
| `chosen` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation choose_take
```
