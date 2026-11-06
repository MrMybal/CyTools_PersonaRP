---
id: operation-verify-voice
title: verify_voice
description: Vérifiez que l’enregistrement de référence est toujours présent et inchangé. Un enregistrement de référence modifié signifie que la voix ne sonnerait plus de la même manière.
section: Référence
order: 200
parent: operations
sourceRevision: 558928e0586f90d1
---

Vérifiez que l’enregistrement de référence est toujours présent et inchangé. Un enregistrement de référence modifié signifie que la voix ne sonnerait plus de la même manière.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `voice_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `id` | `string` | Non | Voir les paramètres de l’opération.  |
| `ok` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `reason` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation verify_voice
```
