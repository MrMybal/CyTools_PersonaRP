---
id: operation-set-relation
title: set_relation
description: Créer ou mettre à jour la façon dont un personnage se sent à l'égard d'un autre, en option écrire le lien symétrique sur le feuille de l'autre personnage également.
section: Référence
order: 200
parent: operations
sourceRevision: 3b27332bedcd50b6
---

Créer ou mettre à jour la façon dont un personnage se sent à l'égard d'un autre, en option écrire le lien symétrique sur le feuille de l'autre personnage également.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `relation` | `object` | Oui | Voir les paramètres de l’opération. `default={}` |
| `reciprocal` | `object` | Non | Rédigé sur l'autre feuille lors de la fourniture.  |
| `mirror` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation set_relation
```
