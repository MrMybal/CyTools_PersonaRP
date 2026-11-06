---
id: operation-speak-batch
title: speak_batch
description: Speak a list of lines — who says what — into a new task folder of data/batches. The list is sent inline: text holds a script ("Name: line", or "ID | Name: line"), a CSV or a JSON list (format auto recognises them), or items…
section: Reference
order: 200
parent: operations
revision: 96aef527cc111926
---

Speak a list of lines — who says what — into a new task folder of data/batches. The list is sent inline: text holds a script ("Name: line", or "ID | Name: line"), a CSV or a JSON list (format auto recognises them), or items gives the lines as objects. Every line gets an id — its own, or its number — and its take is named after it. The folder holds the list as given (source.*), the batch as understood (lot.json), one WAV per line in voix/, and resultats.json / resultats.csv. The lines are generated many at a time in one copy of the voice model; with batch_size 0 the number follows the free VRAM, and a batch that does not fit is halved and tried again, so a large GPU is used to the full. A speaker is found by identifier, name, alias or a part of its name no other character has; voice names a stable voice instead, or on top of the character. A line that cannot be spoken is reported and the batch goes on. dry_run checks the list — speakers, voices, languages — before paying for it. resume continues an earlier task without generating its finished lines again. To read the list or bring characters from files on disk, use speak_batch_file.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `text` | `string` | No | See the operation parameters. `default=""` |
| `format` | `string` | No | See the operation parameters. `default="auto"`, `enum=["auto", "script", "csv", "json"]` |
| `items` | `array` | No | See the operation parameters.  |
| `resume` | `string` | No | See the operation parameters. `default=""` |
| `name` | `string` | No | See the operation parameters. `default=""` |
| `language` | `string` | No | For every line that does not give its own. Empty speaks each character in its own language. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `device` | `string` | No | See the operation parameters. `default="cuda"`, `enum=["cuda", "cpu"]` |
| `batch_size` | `integer` | No | 0 sizes the batches to the free VRAM. `default=0`, `minimum=0`, `maximum=64` |
| `seed` | `integer` | No | See the operation parameters. `default=42`, `minimum=0`, `maximum=2147483647` |
| `precision` | `string` | No | auto: bfloat16 on cards that compute it natively (A100, L4, RTX 30/40), float16 on older ones (T4), float32 on the CPU. `default="auto"`, `enum=["auto", "bfloat16", "float16", "float32"]` |
| `dry_run` | `boolean` | No | Read the list and say who would speak each line with which voice. Generates nothing, makes no folder, needs no GPU. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `batch` | `string` | No | See the operation parameters.  |
| `folder` | `string` | No | See the operation parameters.  |
| `lines` | `integer` | No | See the operation parameters.  |
| `done` | `integer` | No | See the operation parameters.  |
| `failed` | `integer` | No | See the operation parameters.  |
| `skipped` | `integer` | No | See the operation parameters.  |
| `results` | `string` | No | See the operation parameters.  |
| `dryRun` | `boolean` | No | See the operation parameters.  |
| `ready` | `integer` | No | See the operation parameters.  |
| `preview` | `array` | No | See the operation parameters.  |
| `groups` | `array` | No | See the operation parameters.  |
| `errors` | `array` | No | See the operation parameters.  |
| `personas` | `array` | No | See the operation parameters.  |
| `problems` | `array` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation speak_batch
```
