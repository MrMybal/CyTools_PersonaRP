---
id: operation-install-llm
title: install_llm
description: Téléchargez, reprenez ou réparez les poids d'un modèle de catalogue. La licence doit être acceptée personnellement en premier.
section: Référence
order: 200
parent: operations
sourceRevision: a1354fa71337710f
---

Téléchargez, reprenez ou réparez les poids d'un modèle de catalogue. La licence doit être acceptée personnellement en premier.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `accept_license` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `model` | `string` | Non | Voir les paramètres de l’opération.  |
| `installed` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `sizeBytes` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_llm
```
