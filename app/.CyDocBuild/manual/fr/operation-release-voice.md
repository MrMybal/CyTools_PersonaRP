---
id: operation-release-voice
title: release_voice
description: Arrêtez les processus de parole et libérez leurs RAM et VRAM.
section: Référence
order: 200
parent: operations
sourceRevision: 95d261f857e43940
---

Arrêtez les processus de parole et libérez leurs RAM et VRAM.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `released` | `boolean` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation release_voice
```
