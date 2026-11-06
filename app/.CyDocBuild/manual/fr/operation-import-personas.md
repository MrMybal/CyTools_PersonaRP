---
id: operation-import-personas
title: import_personas
description: Lisez un ensemble, une feuille unique ou un monde unique. Les identifiants existants ne sont jamais surécrits : un conflit produit un nouvel identifiant sauf si rename est désactivé.
section: Référence
order: 200
parent: operations
sourceRevision: 2f018d05e4feba5c
---

Lisez un ensemble, une feuille unique ou un monde unique. Les identifiants existants ne sont jamais surécrits : un conflit produit un nouvel identifiant sauf si rename est désactivé.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `rename` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `personas` | `array` | Non | Voir les paramètres de l’opération.  |
| `worlds` | `array` | Non | Voir les paramètres de l’opération.  |
| `voices` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation import_personas
```
