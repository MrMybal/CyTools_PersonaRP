---
id: operation-unload-model
title: unload_model
description: Arrêtez le serveur de conversation et libérez sa réservation RAM et VRAM.
section: Référence
order: 200
parent: operations
sourceRevision: 42ddaa33672068f5
---

Arrêtez le serveur de conversation et libérez sa réservation RAM et VRAM.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `loaded` | `boolean` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation unload_model
```
