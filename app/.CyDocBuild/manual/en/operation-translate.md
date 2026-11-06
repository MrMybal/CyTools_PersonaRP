---
id: operation-translate
title: translate
description: Translate a stored scene, or a single text, with a language model of your choice. The translation is written beside each turn — the original is never changed — so a scene can carry several languages. Delivery marks such as…
section: Reference
order: 200
parent: operations
revision: 6be8b0f71efed5a1
---

Translate a stored scene, or a single text, with a language model of your choice. The translation is written beside each turn — the original is never changed — so a scene can carry several languages. Delivery marks such as [ton: ...] or [pause: 400ms] are masked before translation and put back afterwards; any the model loses are reported. The answer is constrained to one string per turn. Every request carries the context the words need, never translated itself: the world (genre, tone, setting, the places, factions and terms mentioned first), who speaks and how, where the scene stands, the lines just before in their original words, and your own note in context. A text given together with session_id is translated in the light of that scene, and nothing is stored. The places, factions and terms of the world read the same in every translation: each is rendered once per language, recorded in the world (term_translations; see translation_terms), required in every request, and a line that drops one is asked again once — termsMissed reports what still does.

## Parameters {#contract}

| Name | Type | Required | Description |
|---|---|---|---|
| `persona_id` | `string` | No | See the operation parameters. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | No | See the operation parameters. `default=""` |
| `text` | `string` | No | See the operation parameters. `default=""` |
| `world_id` | `string` | No | The world of a text given without a character; a character brings its own. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `context` | `string` | No | See the operation parameters. `default=""` |
| `keep_terms` | `boolean` | No | The places, factions and glossary terms a text mentions are rendered once per language and recorded in the world, so every later translation says them the same way. Off: rendered for this request only. `default=true` |
| `target_language` | `string` | Yes | See the operation parameters. `enum=["French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `source_language` | `string` | No | Empty uses the character's spoken language. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `turns` | `array` | No | See the operation parameters. `default=[]` |
| `roles` | `string` | No | all: both sides of the scene. assistant: the character only. `default="all"`, `enum=["all", "assistant"]` |
| `overwrite` | `boolean` | No | See the operation parameters. `default=false` |
| `save` | `boolean` | No | See the operation parameters. `default=true` |
| `llm_model` | `string` | No | See the operation parameters. `default=""` |
| `device` | `string` | No | Empty keeps the device recorded on the character sheet. `default=""`, `enum=["", "cpu", "cuda"]` |
| `temperature` | `number/null` | No | Empty uses 0.2: a translation is not a place for invention. `default=null`, `minimum=0`, `maximum=2` |
| `seed` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `threads` | `integer/null` | No | See the operation parameters. `default=null`, `minimum=1`, `maximum=64` |
| `keep_loaded` | `boolean` | No | See the operation parameters. `default=false` |
## Returns {#returns}

| Name | Type | Required | Description |
|---|---|---|---|
| `language` | `string` | No | See the operation parameters.  |
| `source` | `string` | No | See the operation parameters.  |
| `model` | `string` | No | See the operation parameters.  |
| `device` | `string` | No | See the operation parameters.  |
| `translations` | `array` | No | See the operation parameters.  |
| `skipped` | `array` | No | See the operation parameters.  |
| `text` | `string` | No | See the operation parameters.  |
| `seconds` | `number` | No | See the operation parameters.  |
| `saved` | `boolean` | No | See the operation parameters.  |
| `sessionId` | `string` | No | See the operation parameters.  |
| `marksLost` | `integer` | No | See the operation parameters.  |
| `file` | `string` | No | See the operation parameters.  |
| `worldId` | `string` | No | See the operation parameters.  |
| `terms` | `object` | No | See the operation parameters.  |
| `termsLearned` | `array` | No | See the operation parameters.  |
| `termsRejected` | `array` | No | See the operation parameters.  |
| `termsRetried` | `integer` | No | See the operation parameters.  |
| `termsMissed` | `integer` | No | See the operation parameters.  |
| `context` | `boolean` | No | See the operation parameters.  |

## Behaviour and access {#behaviour}

- Required permissions: none declared.
- Backends: none declared.
- Cancellation: supported.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation translate
```
