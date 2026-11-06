---
id: operation-save-assistant-thread
title: save_assistant_thread
description: Conserve le titre, les instructions en attente, le brouillon non envoyé et les paramètres du modèle de la discussion sans envoyer rien.
section: Référence
order: 200
parent: operations
sourceRevision: 3bfa2c0aa525b775
---

Conserve le titre, les instructions en attente, le brouillon non envoyé et les paramètres du modèle de la discussion sans envoyer rien.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `thread_id` | `string` | Oui | Voir les paramètres de l’opération. `default=""` |
| `title` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `system` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `draft` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `llm_model` | `string` | Non | Voir les paramètres de l’opération. `default=""` |
| `device` | `string` | Non | Voir les paramètres de l’opération. `default=""`, `enum=["", "cpu", "cuda"]` |
| `temperature` | `number/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=0`, `maximum=2` |
| `response_length` | `integer/null` | Non | Voir les paramètres de l’opération. `default=null`, `minimum=16`, `maximum=4096` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `thread` | `object` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : aucune déclarée.
- Moteurs : aucun déclaré.
- Annulation : non déclarée.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation save_assistant_thread
```
