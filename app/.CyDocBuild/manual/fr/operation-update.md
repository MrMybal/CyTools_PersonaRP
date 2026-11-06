---
id: operation-update
title: update
description: Vérifiez, préparez, activez ou annulez la mise en œuvre ou le moteur. Les poids suivent leur propre catalogue. data/ ne fait jamais partie d'une remplacement.
section: Référence
order: 200
parent: operations
sourceRevision: 1ea81d8f79d7096f
---

Vérifiez, préparez, activez ou annulez la mise en œuvre ou le moteur. Les poids suivent leur propre catalogue. data/ ne fait jamais partie d'une remplacement.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `kind` | `string` | Non | Voir les paramètres de l’opération. `default="engine"`, `enum=["app", "engine"]` |
| `action` | `string` | Non | Voir les paramètres de l’opération. `default="check"`, `enum=["check", "download", "activate", "rollback"]` |
| `repository` | `string` | Non | Vide utilise le dépôt que cette application fournit (release.json). `default=""` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `message` | `string` | Non | Voir les paramètres de l’opération.  |
| `version` | `string` | Non | Voir les paramètres de l’opération.  |
| `updateAvailable` | `boolean` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation update
```
