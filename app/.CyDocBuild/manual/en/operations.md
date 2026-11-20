---
id: operations
title: Automation and API
description: Connect a client and inspect the available operations.
section: Reference
order: 80
parent: overview
revision: f2297e1bc1e02c4c
---

## Command line {#cli}

From the application root, use the private Python interpreter. `describe` and `list-operations` inspect the public contract.

```powershell
runtime\python\Scripts\python.exe app\tool.py describe
runtime\python\Scripts\python.exe app\tool.py list-operations
runtime\python\Scripts\python.exe app\tool.py invoke list_personas --params "{}"
```

## MCP {#mcp}

Configure your MCP client to start the private interpreter with `app/tool.py mcp`, using the application folder as its working directory. Restart the connection when its exposed operation catalogue changes.

## Task files {#task-files}

Local file inputs accept absolute readable paths and are imported into the task workspace automatically. Export wanted results before finishing the task. Do not rely on temporary paths after task cleanup.

## Operations {#operations}

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


## Native communication {#native-communication}

The Windows package includes CyToolsCore 0.12.0 and the native CyMCPSDK 0.7.1
communication library. The same complete operation parameters are available to AI
clients and the standalone application. Run `ai_communication_status` with
`includeOperations: true` to inspect the effective catalogue. This does not contact
an AI provider or generate content.

CLI-generated files are temporary by default. Add `--export-dir` followed by an
absolute destination outside the job store when you want to keep them. In MCP,
export with `cy_export_job` before `cy_finish_task`. The original input file, installed
models, conversations and project documents are not removed by task cleanup.

For the first upgrade from a 0.10.x Core, install the full Windows package.
Application-only updates cannot add the required native library to an older runtime.
Model and provider integrations keep their existing compatibility and permissions;
this upgrade does not make an unsupported model or platform supported.


## Local MCP access {#local-mcp-access}

Core **0.12.0** embeds native CyMCPSDK commit **`34d4bca`**. From the Tool root, start
the local service explicitly:

```powershell
runtime/python/Scripts/python.exe app/tool.py --data-dir data/jobs serve --port 8766
```

Free is the initial profile: connect using only `http://127.0.0.1:8766/mcp`. All exposed
operations are callable without a token or additional transport approval. Arguments,
licence acceptance and explicit destructive-action confirmations remain business rules.
The portable API is at `/v1`; the listener binds only to 127.0.0.1.

Missing choices migrate to Free; explicit profiles are preserved. Use the server option
`--access-profile free`, `--access-profile local_controlled`, `--access-profile token_only`
or `--access-profile protected_access`. Local controlled applies host-selected permissions.
Token only and Protected require a valid token; Protected retains credential permissions.
With the command above, the choice persists in `data/jobs/communication.json`. Restart
the service to change the active profile. CLI/embedded and chat-provider permissions
are unchanged. Use `ai_communication_status` with `includeOperations: true` for discovery.

Install the full Windows package for this native runtime update; app-only updates reject
the old runtime ABI. For a local source upgrade, install the bundled wheel:

```powershell
runtime/python/Scripts/python.exe -m pip install --no-deps app/packages/cytools_core-0.12.0-py3-none-win_amd64.whl
```

Export wanted task files before `cy_finish_task`. Task cleanup preserves original inputs,
installed models, conversations and persistent project documents. Windows x64 is the
validated platform for this update; Linux/macOS native builds require target validation.
