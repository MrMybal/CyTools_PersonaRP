---
id: operation-diagnose-backend
title: diagnose_backend
description: Modèles, moteurs, appareils, comptes de bibliothèques et le disque de stockage en usage.
section: Référence
order: 200
parent: operations
sourceRevision: 7bb074e52142e16c
---

Modèles, moteurs, appareils, comptes de bibliothèques et le disque de stockage en usage.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `verify` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `models` | `array` | Non | Voir les paramètres de l’opération.  |
| `engine` | `object` | Non | Voir les paramètres de l’opération.  |
| `library` | `object` | Non | Voir les paramètres de l’opération.  |
| `platform` | `string` | Non | Voir les paramètres de l’opération.  |
| `resident` | `object` | Non | Voir les paramètres de l’opération.  |
| `paths` | `object` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation diagnose_backend
```
