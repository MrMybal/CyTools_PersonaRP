---
id: guide-app-comfyui-cytools-personarp-lisez-moi
title: Nodes CyTools PersonaRP for ComfyUI
description: Nodes CyTools PersonaRP for ComfyUI
section: Guide
order: 40
parent: guide-lisez-moi
revision: 53ca75917b77f1c9
---

## Nodes CyTools PersonaRP for ComfyUI {#nodes-cytools-personarp-pour-comfyui}

These nodes bring your PersonaRP characters into ComfyUI: their appearance for image models, their dialogues with the scene's image and video prompts, their voice, and everything else from the tool. They are in the category CyTools/PersonaRP.

## Installation {#installation}

From PersonaRP: Library › ComfyUI, click Install here next to your ComfyUI (installations of Comfy Desktop are found automatically), or Install in this folder for another ComfyUI. From the command line, the `install_comfyui_nodes` operation does the same thing. Then restart ComfyUI.

The installation copies this folder into `custom_nodes/cytools_personarp` and writes `config.json`, which says where PersonaRP is. Reinstalling replaces the copy; nothing else in ComfyUI is touched. To remove them, simply delete this folder.

## How it works {#comment-ca-marche}

The nodes never import PersonaRP : ComfyUI keeps its Python, PersonaRP keeps its own, its models and its voice engine. They talk to the tool through its API local (address `127.0.0.1`, never the network, with a token). When a node runs and PersonaRP does not respond, ComfyUI starts it with its own Python, then stops it by closing. Opening ComfyUI starts nothing : the menus (characters, voices, models) are read from the tool's files as long as it does not run.

PersonaRP creates the token and stores it in `data/settings`. It does not appear in any workflow or widget.

The ComfyUI progress bar tracks the Tool’s work, and Stop cancels it.

## Graphics memory {#la-memoire-graphique}

A 24 GB card cannot hold an image model, a language model and a voice model at the same time. Nodes that use the GPU have two settings, enabled by default:

- liberer_vram_comfyui: unloads ComfyUI models before requesting work;
- rendre_la_vram_apres: asks PersonaRP to unload its models when finished.

Disable them to chain several PersonaRP nodes without reloading the models.

## Nodes {#les-nodes}

| Node | Inputs | Outputs |
| --- | --- | --- |
| Character | a character | persona_id, name, appearance, visual_labels (ready for a prompt), JSON_sheet |
| Dialogue | character, message, scene (new, continue last, continue a given scene, no memory), stage direction, speak, model, device, seed | response, spoken text, negative prompt, directive JSON, audio, session_id |
| Voice | character, text, language (the voice configuration by language on the sheet applies), stable voice, seed, device | audio, file (copied in `output/personarp`), duration, used voice |
| Scene prompts | directive JSON (of the Dialogue), character | prompt image, prompt video, prompt negative, summary |
| Translate | text, target language, source language, model, character and optional context note, optional session | translation (`[ton: …]` placeholders remain in place), model used |
| Read an image | image, language, vision model | appearance, visual labels, JSON proposal, model used, observation (detailed English description from which the card is derived) |
| Voice task | list (script `ID \ | Name: texte`, CSV or JSON), name, language, batch size, accuracy, character packages (one path per line), check only | task file, summary, results JSON, all chained recordings in one audio |
| Operation PersonaRP (avancé) | any tool operation, JSON parameters | result JSON |

Les sorties AUDIO se connectent aux nœuds audio de ComfyUI (Save Audio, Preview Audio…), les sorties texte se connectent à tout encodeur de prompt.

Provide context for the translation. A single isolated sentence can be ambiguous: without context, 'the col' has been translated as 'the gate' and 'the collar'. Choose a character: their world (locations, terms, tone), their way of speaking, and the scene they are in accompany the request. Add a session_id to include the preceding lines and write in context what they do not say ('at the foot of a snow-covered col'). None of this context is translated. With '(that of the sheet)' and without a character, it is the assistant's model that translates — often a role-playing game model; the `modele_utilise` output indicates who did the translation.

## Settings {#reglages}

`config.json` : `tool_root` (the PersonaRP folder), `port` (8791 by default), `auto_start`. The environment variable `PERSONARP_TOOL_ROOT` replaces `tool_root`.

Server log started by ComfyUI : `data/logs/comfyui-server.log` in PersonaRP.
