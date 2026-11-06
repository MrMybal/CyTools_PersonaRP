---
id: operation-set-term-translations
title: set_term_translations
description: Définissez la représentation d'un terme dans une langue. Une représentation définie ici ne sera jamais remplacée par le modèle ; un texte vide l'oublie, de sorte que la prochaine traduction la rendra à nouveau.
section: Référence
order: 200
parent: operations
sourceRevision: 50214c467a2575a1
---

Définissez la représentation d'un terme dans une langue. Une représentation définie ici ne sera jamais remplacée par le modèle ; un texte vide l'oublie, de sorte que la prochaine traduction la rendra à nouveau.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `language` | `string` | Oui | Voir les paramètres de l’opération. `enum=["French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `terms` | `array` | Oui | Voir les paramètres de l’opération.  |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `worldId` | `string` | Non | Voir les paramètres de l’opération.  |
| `language` | `string` | Non | Voir les paramètres de l’opération.  |
| `changed` | `array` | Non | Voir les paramètres de l’opération.  |
| `revision` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation set_term_translations
```
