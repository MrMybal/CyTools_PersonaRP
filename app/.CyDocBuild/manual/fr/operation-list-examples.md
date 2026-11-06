---
id: operation-list-examples
title: list_examples
description: Les mondes d'exemple fournis avec l'Outil — épique fantasy, science-fiction, cyberpunk, gothique horreur, post-apocalypse, fantasy douce — chacun un ensemble d'un monde et de son casting. Importez-en un avec importpersonas et…
section: Référence
order: 200
parent: operations
sourceRevision: 8c5092a2c2c4c699
---

Les mondes d'exemple fournis avec l'Outil — épique fantasy, science-fiction, cyberpunk, gothique horreur, post-apocalypse, fantasy douce — chacun un ensemble d'un monde et de son casting. Importez-en un avec import_personas et le fichier donné ici ; une importation est une copie, et un identifiant existant ne sera jamais surécrit.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `examples` | `array` | Non | Voir les paramètres de l’opération.  |
| `folder` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_examples
```
