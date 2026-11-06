---
id: operation-create-world
title: create_world
description: Créer un document partagé de la légende.
section: Référence
order: 200
parent: operations
sourceRevision: 78dbb073c1c7c823
---

Créer un document partagé de la légende.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world` | `object` | Non | Voir les paramètres de l’opération.  |
| `name` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `world` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation create_world
```
