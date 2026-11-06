---
id: operation-install-cuda
title: install_cuda
description: Téléchargez et vérifiez la version Windows x64 CUDA de llama.cpp, puis testez-la contre le pilote installé avant de l'enregistrer.
section: Référence
order: 200
parent: operations
sourceRevision: 1ae0ae83e4a57efb
---

Téléchargez et vérifiez la version Windows x64 CUDA de llama.cpp, puis testez-la contre le pilote installé avant de l'enregistrer.

## Paramètres {#contract}

Aucun champ nommé n’est déclaré à ce niveau. Consultez le schéma avec `describe-operation` pour connaître sa forme exacte.
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `installed` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `version` | `string` | Non | Voir les paramètres de l’opération.  |
| `devices` | `string` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_cuda
```
