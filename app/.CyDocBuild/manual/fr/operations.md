---
id: operations
title: Automatisation et API
description: Connectez un client et consultez les opérations disponibles.
section: Référence
order: 80
parent: overview
sourceRevision: 38c38af8e8f9b472
---

## Ligne de commande {#cli}

Depuis la racine de l’application, utilisez son interpréteur Python privé. `describe` et `list-operations` examinent le contrat public.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe
runtime\python\Scripts\python.exe app\tool.py list-operations
runtime\python\Scripts\python.exe app\tool.py invoke list_personas --params "{}"
```

## MCP {#mcp}

Configurez votre client MCP pour lancer l’interpréteur privé avec `app/tool.py mcp`, en utilisant le dossier de l’application comme dossier de travail. Reconnectez-le lorsque le catalogue d’opérations exposées change.

## Fichiers des tâches {#task-files}

Les entrées locales acceptent des chemins absolus lisibles et sont importées automatiquement dans l’espace de la tâche. Exportez les résultats utiles avant de terminer la tâche. Ne réutilisez pas les chemins temporaires après nettoyage.

## Opérations {#operations}

- [`chat`](doc:operation-chat)
- [`preview_prompt`](doc:operation-preview-prompt)
- [`author`](doc:operation-author)
- [`apply_proposal`](doc:operation-apply-proposal)
- [`list_personas`](doc:operation-list-personas)
- [`get_persona`](doc:operation-get-persona)
- [`create_persona`](doc:operation-create-persona)
- [`save_persona`](doc:operation-save-persona)
- [`duplicate_persona`](doc:operation-duplicate-persona)
- [`remove_persona`](doc:operation-remove-persona)
- [`persona_revisions`](doc:operation-persona-revisions)
- [`restore_persona`](doc:operation-restore-persona)
- [`list_worlds`](doc:operation-list-worlds)
- [`get_world`](doc:operation-get-world)
- [`create_world`](doc:operation-create-world)
- [`save_world`](doc:operation-save-world)
- [`remove_world`](doc:operation-remove-world)
- [`set_relation`](doc:operation-set-relation)
- [`drop_relation`](doc:operation-drop-relation)
- [`remember`](doc:operation-remember)
- [`export_personas`](doc:operation-export-personas)
- [`list_examples`](doc:operation-list-examples)
- [`import_personas`](doc:operation-import-personas)
- [`list_sessions`](doc:operation-list-sessions)
- [`get_session`](doc:operation-get-session)
- [`new_session`](doc:operation-new-session)
- [`remove_session`](doc:operation-remove-session)
- [`translate`](doc:operation-translate)
- [`speak_turn`](doc:operation-speak-turn)
- [`choose_take`](doc:operation-choose-take)
- [`remove_take`](doc:operation-remove-take)
- [`speak_batch`](doc:operation-speak-batch)
- [`speak_batch_file`](doc:operation-speak-batch-file)
- [`comfyui_nodes_status`](doc:operation-comfyui-nodes-status)
- [`install_comfyui_nodes`](doc:operation-install-comfyui-nodes)
- [`list_batches`](doc:operation-list-batches)
- [`translation_terms`](doc:operation-translation-terms)
- [`set_term_translations`](doc:operation-set-term-translations)
- [`scene_prompts`](doc:operation-scene-prompts)
- [`assistant_chat`](doc:operation-assistant-chat)
- [`list_assistant_threads`](doc:operation-list-assistant-threads)
- [`new_assistant_thread`](doc:operation-new-assistant-thread)
- [`get_assistant_thread`](doc:operation-get-assistant-thread)
- [`save_assistant_thread`](doc:operation-save-assistant-thread)
- [`remove_assistant_thread`](doc:operation-remove-assistant-thread)
- [`list_images`](doc:operation-list-images)
- [`add_persona_image`](doc:operation-add-persona-image)
- [`remove_persona_image`](doc:operation-remove-persona-image)
- [`verify_persona_images`](doc:operation-verify-persona-images)
- [`describe_image`](doc:operation-describe-image)
- [`speak`](doc:operation-speak)
- [`capture_voice_take`](doc:operation-capture-voice-take)
- [`create_stable_voice`](doc:operation-create-stable-voice)
- [`list_voices`](doc:operation-list-voices)
- [`verify_voice`](doc:operation-verify-voice)
- [`remove_voice`](doc:operation-remove-voice)
- [`transcribe`](doc:operation-transcribe)
- [`list_voice_models`](doc:operation-list-voice-models)
- [`install_voice_model`](doc:operation-install-voice-model)
- [`install_voice_engine`](doc:operation-install-voice-engine)
- [`release_voice`](doc:operation-release-voice)
- [`list_models`](doc:operation-list-models)
- [`install_llm`](doc:operation-install-llm)
- [`install_cuda`](doc:operation-install-cuda)
- [`unload_model`](doc:operation-unload-model)
- [`diagnose_backend`](doc:operation-diagnose-backend)
- [`update`](doc:operation-update)
