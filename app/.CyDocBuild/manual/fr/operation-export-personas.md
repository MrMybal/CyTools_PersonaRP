---
id: operation-export-personas
title: export_personas
description: Écrivez un ensemble autonome : les feuilles, leur monde, leurs décripteurs de voix, et optionnellement les enregistrements de référence sous forme d'un .zip et les scènes jouées avec eux. Une scène importée suit son personnage…
section: Référence
order: 200
parent: operations
sourceRevision: 1ae4b34fa5146ac0
---

Écrivez un ensemble autonome : les feuilles, leur monde, leurs décripteurs de voix, et optionnellement les enregistrements de référence sous forme d'un .zip et les scènes jouées avec eux. Une scène importée suit son personnage sous un nouvel identifiant.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_ids` | `array` | Oui | Voir les paramètres de l’opération. `default=[]` |
| `destination` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `include_world` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `include_voice` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `include_audio` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `include_images` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `include_sessions` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `personas` | `array` | Non | Voir les paramètres de l’opération.  |
| `worlds` | `array` | Non | Voir les paramètres de l’opération.  |
| `voices` | `array` | Non | Voir les paramètres de l’opération.  |
| `bundledAudio` | `integer` | Non | Voir les paramètres de l’opération.  |
| `bundledImages` | `integer` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation export_personas
```
