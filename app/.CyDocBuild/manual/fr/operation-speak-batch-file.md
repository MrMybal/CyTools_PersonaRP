---
id: operation-speak-batch-file
title: speak_batch_file
description: speakbatch, avec des fichiers : la liste lue depuis un fichier (un scénario .txt, un CSV .csv/.tsv ou une liste .json du JSON; le texte ou les éléments fonctionnent toujours), et personas, les personnages que le travail…
section: Référence
order: 200
parent: operations
sourceRevision: a059b5160bebebe7
---

speak_batch, avec des fichiers : la liste lue depuis un fichier (un scénario .txt, un CSV .csv/.tsv ou une liste .json du JSON; le texte ou les éléments fonctionnent toujours), et personas, les personnages que le travail apporte — des ensembles exportés par PersonaRP avec leurs enregistrements (feuille, monde, voix stables, les voix par langue incluses). Ils sont copiés dans le dossier du travail (personnages/) et ne sont jamais dans la bibliothèque, et sont recherchés avant la bibliothèque; use_library false garde le travail à ses propres personnages. Le dossier contient la liste telle quelle (source.*), le lot compris (lot.json), un WAV par ligne dans voix/, et resultats.json / resultats.csv. Les lignes sont générées à la fois dans une seule copie du modèle de voix; avec batch_size 0 le nombre suit la disponibilité du VRAM, et un lot qui ne s'ajuste pas est divisé par deux et tenté à nouveau, donc un grand GPU est utilisé jusqu'à la fin. Un locuteur est trouvé par identifiant, nom, surnom ou une partie de son nom que nul autre personnage n'a; la voix nomme une voix stable au lieu de cela, ou en plus du personnage. Une ligne qui ne peut pas être prononcée est signalée et le lot continue. dry_run vérifie la liste — locuteurs, voix, langues — avant de payer pour cela.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `file` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `personas` | `array` | Non | Voir les paramètres de l’opération.  |
| `use_library` | `boolean` | Non | Désactivé : seulement les personnages et voix que le travail a apportés. `default=true` |
| `text` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `format` | `string` | Non | Voir les paramètres de l’opération. `default="auto"`, `enum=["auto", "script", "csv", "json"]` |
| `items` | `array` | Non | Voir les paramètres de l’opération.  |
| `name` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `language` | `string` | Non | Pour chaque ligne qui ne s'exprime pas à elle-même. Le vide fait parler chaque personnage dans sa propre langue. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `batch_size` | `integer` | Non | 0 ajuste les lots à la disponibilité du VRAM. `default=0`, `minimum=0`, `maximum=64` |
| `seed` | `integer` | Non | Voir les paramètres de l’opération. `default=42`, `minimum=0`, `maximum=2147483647` |
| `precision` | `string` | Non | auto: bfloat16 sur les cartes qui le calculent nativement (A100, L4, RTX 30/40), float16 sur les plus anciennes (T4), float32 sur le CPU. `default="auto"`, `enum=["auto", "bfloat16", "float16", "float32"]` |
| `dry_run` | `boolean` | Non | Lisez la liste et dites qui parlerait chaque ligne avec quelle voix. Génère rien, ne crée pas de dossier, n'a pas besoin du GPU. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `batch` | `string` | Non | Voir les paramètres de l’opération.  |
| `folder` | `string` | Non | Voir les paramètres de l’opération.  |
| `lines` | `integer` | Non | Voir les paramètres de l’opération.  |
| `done` | `integer` | Non | Voir les paramètres de l’opération.  |
| `failed` | `integer` | Non | Voir les paramètres de l’opération.  |
| `skipped` | `integer` | Non | Voir les paramètres de l’opération.  |
| `results` | `string` | Non | Voir les paramètres de l’opération.  |
| `dryRun` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `ready` | `integer` | Non | Voir les paramètres de l’opération.  |
| `preview` | `array` | Non | Voir les paramètres de l’opération.  |
| `groups` | `array` | Non | Voir les paramètres de l’opération.  |
| `errors` | `array` | Non | Voir les paramètres de l’opération.  |
| `personas` | `array` | Non | Voir les paramètres de l’opération.  |
| `problems` | `array` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `filesystemExternal`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak_batch_file
```
