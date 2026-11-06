---
id: operation-install-voice-engine
title: install_voice_engine
description: Créez ou réparez l’environnement de speech privé (PyTorch, Qwen3-TTS, Whisper) à son emplacement final, puis importez-le et vérifiez-le. Rien n’est enregistré comme installé avant que cela ne passe.
section: Référence
order: 200
parent: operations
sourceRevision: 7d294caa8236cfdc
---

Créez ou réparez l’environnement de speech privé (PyTorch, Qwen3-TTS, Whisper) à son emplacement final, puis importez-le et vérifiez-le. Rien n’est enregistré comme installé avant que cela ne passe.

## Paramètres {#contract}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `cpu_only` | `boolean` | Non | Voir les paramètres de l’opération. `default=false` |
## Retours {#returns}

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `installed` | `boolean` | Non | Voir les paramètres de l’opération.  |
| `log` | `string` | Non | Voir les paramètres de l’opération.  |
| `report` | `object` | Non | Voir les paramètres de l’opération.  |

## Comportement et accès {#behaviour}

- Autorisations requises : `network`
- Moteurs : aucun déclaré.
- Annulation : prise en charge.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe-operation install_voice_engine
```
