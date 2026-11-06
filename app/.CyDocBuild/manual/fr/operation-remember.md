---
id: operation-remember
title: remember
description: Appliquez des faits, des épisodes et l'état actuel à un personnage. La mémoire est toujours explicite : rien n'est extraite d'une conversation sans cette appel.
section: Référence
order: 200
parent: operations
sourceRevision: 6f9e0e8c49a3f52c
---

Appliquez des faits, des épisodes et l'état actuel à un personnage. La mémoire est toujours explicite : rien n'est extraite d'une conversation sans cette appel.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `facts` | `array` | Non | Voir les paramètres de l’opération. `default=[]` |
| `episodes` | `array` | Non | Voir les paramètres de l’opération. `default=[]` |
| `state` | `object` | Non | Ce qui change au fil de l'histoire.  |
| `replace_facts` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona` | `object` | Non | Voir les paramètres de l’opération. `default={}` |
| `added` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation remember
```
