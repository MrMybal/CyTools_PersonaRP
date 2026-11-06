---
id: operation-remove-take
title: remove_take
description: Déplace une prise d'une ligne dans la corbeille à côté des prises de scène (data/sessions/<character>/audio/<session>/.trash) ; rien n'est supprimé. Si c'était la prise qui faisait jouer la ligne, la dernière prise restante…
section: Référence
order: 200
parent: operations
sourceRevision: 2b91178e6326f676
---

Déplace une prise d'une ligne dans la corbeille à côté des prises de scène (data/sessions/<character>/audio/<session>/.trash) ; rien n'est supprimé. Si c'était la prise qui faisait jouer la ligne, la dernière prise restante est jouée à la place.

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
| `trash` | `string` | Non | Voir les paramètres de l’opération.  |
| `left` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remove_take
```
