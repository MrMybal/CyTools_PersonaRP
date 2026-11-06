---
id: operation-list-models
title: list_models
description: Catalogue avec l'état d'installation, la taille, les octets présents, la licence et la source.
section: Référence
order: 200
parent: operations
sourceRevision: 9a8fc7df742a9785
---

Catalogue avec l'état d'installation, la taille, les octets présents, la licence et la source.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `verify` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `models` | `array` | Non | Voir les paramètres de l’opération.  |
| `engine` | `object` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation list_models
```
