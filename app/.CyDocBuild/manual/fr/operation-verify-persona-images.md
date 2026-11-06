---
id: operation-verify-persona-images
title: verify_persona_images
description: Vérifie que chaque photographie d'un feuillet est toujours présente et inchangée.
section: Référence
order: 200
parent: operations
sourceRevision: 24aa64013713f4ba
---

Vérifie que chaque photographie d'un feuillet est toujours présente et inchangée.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `references` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation verify_persona_images
```
