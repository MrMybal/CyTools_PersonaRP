---
id: operation-list-batches
title: list_batches
description: Chaque dossier de lot dans data/batches, le plus récent en premier, avec le nombre de lignes qu'il a faites.
section: Référence
order: 200
parent: operations
sourceRevision: 2c46c688caf11118
---

Chaque dossier de lot dans data/batches, le plus récent en premier, avec le nombre de lignes qu'il a faites.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `folder` | `string` | Non | Voir les paramètres de l’opération.  |
| `batches` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_batches
```
