---
id: operation-speak-batch
title: speak_batch
description: Lire une liste de lignes — qui dit quoi — dans un nouveau dossier de tâches de data/batches. La liste est envoyée en ligne : le texte contient un scénario ("Nom: ligne", ou "ID | Nom: ligne"), un CSV ou un JSON (le format est…
section: Référence
order: 200
parent: operations
sourceRevision: 96aef527cc111926
---

Lire une liste de lignes — qui dit quoi — dans un nouveau dossier de tâches de data/batches. La liste est envoyée en ligne : le texte contient un scénario ("Nom: ligne", ou "ID | Nom: ligne"), un CSV ou un JSON (le format est reconnu automatiquement), ou items donne les lignes comme des objets. Chaque ligne a un identifiant — son propre ou son numéro — et son enregistrement est nommé d'après elle. Le dossier contient la liste telle qu'elle est donnée (source.*), le lot compris (lot.json), un WAV par ligne dans voix/, et resultats.json / resultats.csv. Les lignes sont générées en même temps en grand nombre dans une seule copie du modèle de voix ; avec batch_size 0, le nombre suit le libre VRAM, et un lot qui ne s'ajuste pas est divisée par deux et tentée à nouveau, donc un grand GPU est utilisé jusqu'au bout. Un locuteur est trouvé par identifiant, nom, surnom ou une partie de son nom que nul autre personnage n'a ; le nom d'une voix désigne une voix stable au lieu du personnage, ou en plus du personnage. Une ligne qui ne peut pas être prononcée est signalée et le lancement continue. dry_run vérifie la liste — locuteurs, voix, langues — avant de la facturer. resume continue une tâche précédente sans générer à nouveau ses lignes terminées. Pour lire la liste ou apporter des personnages depuis des fichiers sur le disque, utilisez speak_batch_file.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `text` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `format` | `string` | Non | Voir les paramètres de l’opération. `default="auto"`, `enum=["auto", "script", "csv", "json"]` |
| `items` | `array` | Non | Voir les paramètres de l’opération.  |
| `resume` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
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

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak_batch
```
