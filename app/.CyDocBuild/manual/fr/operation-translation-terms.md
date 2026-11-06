---
id: operation-translation-terms
title: translation_terms
description: Les lieux, factions et termes du glossaire d'un monde, chacun avec sa représentation dans une langue, d'où il vient (modèle ou personnage) et quel modèle l'a rendu.
section: Référence
order: 200
parent: operations
sourceRevision: ccfe1a3c9f477fb8
---

Les lieux, factions et termes du glossaire d'un monde, chacun avec sa représentation dans une langue, d'où il vient (modèle ou personnage) et quel modèle l'a rendu.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `language` | `string` | Oui | Voir les paramètres de l’opération. `enum=["French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `worldId` | `string` | Non | Voir les paramètres de l’opération.  |
| `language` | `string` | Non | Voir les paramètres de l’opération.  |
| `terms` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation translation_terms
```
