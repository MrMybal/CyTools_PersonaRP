---
id: operation-translate
title: translate
description: Traduire une scène enregistrée, ou un seul texte, avec un modèle de langue de votre choix. La traduction est écrite à côté de chaque tour — l'original n'est jamais modifié — de sorte qu'une scène peut porter plusieurs langues.…
section: Référence
order: 200
parent: operations
sourceRevision: 6be8b0f71efed5a1
---

Traduire une scène enregistrée, ou un seul texte, avec un modèle de langue de votre choix. La traduction est écrite à côté de chaque tour — l'original n'est jamais modifié — de sorte qu'une scène peut porter plusieurs langues. Les marques de livraison telles que [ton: ...] ou [pause: 400ms] sont masquées avant la traduction et remises en place après ; tout ce que le modèle perd est signalé. La réponse est contrainte à une chaîne par tour. Chaque demande porte le contexte dont les mots ont besoin, jamais traduit lui-même : le monde (genre, ton, cadre, les lieux, factions et termes mentionnés en premier), qui parle et de quelle manière, où se trouve la scène, les lignes juste avant dans leurs mots originaux, et votre propre note dans ce contexte. Un texte donné avec session_id est traduit en lumière de cette scène, et rien n'est stocké. Les lieux, factions et termes du monde sont les mêmes dans chaque traduction : chacun est rendu une fois par langue, enregistré dans le monde (term_translations; voir translation_terms), requis dans chaque demande, et une ligne qui enlève un est demandée à nouveau une fois — termsMissed rapporte ce qui n'est toujours pas.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `persona_id` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `session_id` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `text` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `world_id` | `string` | Non | Le monde d'un texte donné sans personnage ; un personnage apporte son propre. `default=""`, `pattern="^$|^[a-z0-9][a-z0-9-]{0,79}$"` |
| `context` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `keep_terms` | `boolean` | Non | Les lieux, factions et termes glossaires d'un texte mentionnés sont rendus une fois par langue et enregistrés dans le monde, de sorte que chaque traduction ultérieure les dit de la même manière. Off : rendu pour cette demande uniquement. `default=true` |
| `target_language` | `string` | Oui | Voir les paramètres de l’opération. `enum=["French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `source_language` | `string` | Non | Empty utilise la langue parlée du personnage. `default=""`, `enum=["", "French", "English", "Spanish", "German", "Italian", "Portuguese", "Russian", "Chinese", "Japanese", "Korean"]` |
| `turns` | `array` | Non | Voir les paramètres de l’opération. `default=[]` |
| `roles` | `string` | Non | all: tous les côtés de la scène. assistant: le personnage seulement. `default="all"`, `enum=["all", "assistant"]` |
| `overwrite` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
| `save` | `boolean` | Non | Voir les paramètres de l’opération. `default=true` |
| `llm_model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `device` | `string` | Non | Vide conserve le périphérique enregistré sur la fiche du personnage. `default=""`, `enum=["", "cpu", "cuda"]` |
| `temperature` | `number/null` | Non | Empty utilise 0.2 : une traduction n'est pas un lieu d'invention. `default=null`, `minimum=0`, `maximum=2` |
| `seed` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=-1`, `maximum=2147483647` |
| `threads` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=1`, `maximum=64` |
| `keep_loaded` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `language` | `string` | Non | Voir les paramètres de l’opération.  |
| `source` | `string` | Non | Voir les paramètres de l’opération.  |
| `model` | `string` | Non | Voir les paramètres de l’opération.  |
| `device` | `string` | Non | Voir les paramètres de l’opération.  |
| `translations` | `array` | Non | Voir les paramètres de l’opération.  |
| `skipped` | `array` | Non | Voir les paramètres de l’opération.  |
| `text` | `string` | Non | Voir les paramètres de l’opération.  |
| `seconds` | `number` | Non | Voir les paramètres de l’opération.  |
| `saved` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `sessionId` | `string` | Non | Voir les paramètres de l’opération.  |
| `marksLost` | `integer` | Non | Voir les paramètres de l’opération.  |
| `file` | `string` | Non | Voir les paramètres de l’opération.  |
| `worldId` | `string` | Non | Voir les paramètres de l’opération.  |
| `terms` | `object` | Non | Voir les paramètres de l’opération.  |
| `termsLearned` | `array` | Non | Voir les paramètres de l’opération.  |
| `termsRejected` | `array` | Non | Voir les paramètres de l’opération.  |
| `termsRetried` | `integer` | Non | Voir les paramètres de l’opération.  |
| `termsMissed` | `integer` | Non | Voir les paramètres de l’opération.  |
| `context` | `boolean` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation translate
```
