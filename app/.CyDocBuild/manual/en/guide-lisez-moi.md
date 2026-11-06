---
id: guide-lisez-moi
title: User guide
description: Use the application step by step.
section: Guide
order: 10
parent: overview
revision: 4c877141aece0611
---

## CyTools PersonaRP {#cytools-personarp-0-1-3}

Launch CyTools_PersonaRP.exe. The window opens directly: no terminal, no JSON to write.

No model is provided with the tool. Engines and models are downloaded from the interface, each with its license to accept: see First launch below. PersonaRP keeps its own copies and does not depend on any other tool.

## Install the binary version (Windows x64) {#installer-la-version-binaire-windows-x64}

Each release of the repository (https://github.com/MrMybal/CyTools_PersonaRP/releases) contains `CyTools_PersonaRP-<version>-windows-x64.zip`: the launcher, the application and a private Python 3.11 with everything it needs. Extract the zip in a folder where you can write, then double-click on `CyTools_PersonaRP.exe`: neither Python, nor git, nor compiler are required. Once the speech engine is installed, do not move the folder: this engine is a Python environment linked to its location. `SHA256SUMS.txt` gives the hashes of the release files; `cytools-app.zip` is the application only, used by the Updates tab.

## First launch {#premier-lancement}

1. Models tab: install the conversation engine (CUDA for a card NVIDIA, otherwise CPU), then at least one conversation model. The example sheets are set to Nymphaea RP 4B; any other installed model is selected on the sheet, Models tab.
2. Voice tab: install the speech engine (about 8 GB), then useful voice models — 1.7B Base for stable voices, 1.7B VoiceDesign for inventing a voice, 1.7B CustomVoice for predefined voices, Whisper for transcription.
3. Optional, Models tab: a vision model (Qwen2.5-VL 7B) for reading character photos.

Each download is cancelled and restarted, and is not declared installed until its SHA-256 is verified.

## What the tool does {#ce-que-fait-l-outil}

Create persistent characters, make them live in a shared world, play scenes with them, and retrieve for each line a description of what a camera would see.

- Characters — a complete sheet: identity, appearance, personality, way of speaking, past, current state, memory, relationships, voice, visual direction, and model settings. Each recording creates a revision; the old one is kept and restorable.
- Worlds — the shared lore: locations, factions, laws, timeline, glossary, what must remain true and what never happens. Multiple characters can share a world; each knows who else lives there.
- Relationships — who is who to each other, with a feeling, trust, a shared history, tension, and what is hidden. The reverse link can be written automatically on the other sheet.
- Scenes — a saved conversation by character, replayed exactly as it was later.
- Memory — explicit. Nothing is extracted from a conversation without your addition.
- Assistant — to write a sheet, a world, or a single section. The proposal is reviewed and modifiable; it is applied only if you request it.
- Stable voice — a 12 to 24-second recording captured once, then cloned for all subsequent lines, with gameplay annotations written by the character themselves.
- Import / export — a character is exported with its world and voice sheet — and, if you check Include their scenes, the scenes played with him (the lines, not the takes) —, in a single transportable file.

## Example worlds {#mondes-d-exemple}

Six worlds ready to play are provided, each with three or four complete characters, their relationships and a secret to discover: an epic fantasy in the spirit of great sagas (entirely original), a space station science-fiction, a cyberpunk marseillais, a gothic horror normande, a post-apocalyptic of caravans and a sweet fantasy in the spirit of the Floating Archives.

Library Tab › Examples, Import World button. Import is a copy: the example never changes and an existing character is never overwritten. Files are in `app/examples`, with their presentation in `app/examples/LISEZ-MOI.md`. Each character comes with its stable voice: one can play and hear a scene right after import.

## Image descriptions, video, and movement {#les-descriptions-d-image-de-video-et-de-mouvement}

In the sheet, visual direction tab, activate 'Describe the plan at each response'. At each reply, the tool produces in addition to the dialogue a structured JSON object : look, pose, expression, action, sequence of timed movements, framing, setting, lighting, plus a written image prompt and a video prompt.

This block appears in the conversation, folded under the line, and it is copyable. It is never spoken aloud: it's data, not dialogue. The tool described, it neither creates nor image nor video — the prompt is meant to be directed toward a rendering tool.

By default the description is produced by a forced second pass: the game model writes the line, then a separate pass describes the plan with a grammar that guarantees a JSON valid. This is why the description never overflows into the dialogue. A small roleplay model fills the structure but remains poor; one can choose a larger model for the description alone, without changing the one that plays.

The 'additional targets' allow you to request a specific form expected by a particular tool: give its name, and the descriptor fills a separate entry for it.

## Character photos {#les-photos-de-personnage}

In the sheet, under the Appearance tab, you can attach photographs: a portrait, a full-body shot, an outfit, a detail, an expression, a setting. They are copied next to the character, they go with an export, and the tool signals if one of them has been moved or modified since its addition. The game model never sees them: it only reads text.

### Extract the visual description {#extraire-la-description-visuelle}

Button Describe the character from this photo. A vision model reads the image in two steps. It first looks at: it describes the person in detailed prose (face, skin, hair, eyes, expression, each piece of clothing with its color, material, and patterns, jewelry, bags, marks), where these models are the most precise. Then it writes the Appearance branch from what it has seen: summary, build, face, hair, eyes, skin, outfit, marks, accessories, apparent age — sentences, not isolated words — and especially the visual tags. A field that the photo does not show (build on a portrait) remains empty rather than invented; what slips from another language or alphabet is removed.

These tags are the key point. They are six to twelve groups of words, such as 'black hair updo', 'blue kimono with embroidered stars', 'brown leather bag', which are then taken verbatim in each image prompt for the character. This is what makes it recognizable from one shot to another. The decoding grammar forbids too short tags: 'woman', 'blue', or 'blue eyes' do not identify anyone.

The result is a suggestion, not a direct writing: you read it in the Assistant tab and apply it if it suits you. It only replaces the Appearance branch; memory, past, and relationships are not affected. The model is instructed to describe only what is visible and never to invent a name or story from an image.

The vision model (Qwen2.5-VL 7B, 6 GB) installs from the Models tab, like the others, with license acceptance. It takes about 20 seconds per photo on GPU (both times included).

## The voice {#la-voix}

The voice counts as much as the text: it is what makes a dialogue playable. Voice tab.

### Create a stable voice {#creer-une-voix-stable}

This is the heart of the system, in three steps.

1. Capture a take of 12 to 24 seconds. Either you describe the voice in one sentence ("woman, late twenties, deep and steady, slow pace, contained warmth") and it is created; or you choose a predefined voice; or you provide your own recording — a file, or Record from Microphone in Use Your Own Recording (microphone selection, level displayed, automatic stop at 30 seconds; the WAV is stored in `data/inputs`). The take is automatically transcribed because a clone needs the actual words spoken, not the ones you wanted.
2. Listen. The duration is displayed and the tool says if it is in the right window.
3. Keep. The take becomes a stable voice: locked, recorded fingerprint, tied to the character. All its subsequent lines are cloned from this take, so the voice does not drift from one line to another or from one session to another.

The take is kept next to the library, not in the job's temporary folder: you can pick it up tomorrow. Check if the reference recording has been moved or modified instead of producing a voice that no longer sounds like anything.

### The vocal audio {#le-jeu-vocal}

The character can write their own directions in their lines: `[ton: sourd]`, `[pause: 400ms]`, `[émotion: soulagement]`, `[rythme: lent]`, `[murmure]`, `[emphase: jamais]` — in French as well as in English. A tone remains active until it is changed or reset to `normal`; an emphasis is valid only for its passage. Pauses become real silences at the right duration. None of this is pronounced.

Néanmoins, neither are read: the stage directions between asterisks (adjustable) and the scene description, never.

By default, the way of speaking is derived from the character sheet — personality, style of speech, register, mood at the moment — and the line to which the character is responding. Memory and lore are not injected into the voice command: these are not game elements.

A note on a limitation: a cloned voice does not read any written instructions. The Qwen3-TTS cloning model reproduces its take and does not have an input for direction; therefore, the `[ton: …]`, `[émotion: …]`, and permanent direction instructions only guide invented voices and predefined voices. However, pauses apply to all voices.

Speed and height (in the sheet, Voice tab) are set for each character: ×0.5 to ×2 and ±12 semitones. They are applied after the model, by signal processing (speed does not change the height), to each spoken line — scenes, translations, batches — and never to the take from which a stable voice is drawn, to keep the cloning faithful. A few semitones change the height of a voice; an octave makes it another voice.

Each line keeps all its takes. Redoing a line adds a take instead of replacing the previous one: Take 2 out of 3, the arrows to switch between them (the line plays the one you choose), and Put this take in the trash to exclude it — it goes to `audio/<scène>/.trash`, nothing is deleted.

### Translate a scene and hear it in another language {#traduire-une-scene-et-l-entendre-dans-une-autre-langue}

A scene is written in the language of the character. Then, in the Scene tab, the Translation and voice in other languages:

1. choose the language and the translation model — any installed model, not necessarily the one that plays the character;
2. Translate the scene. The translation is placed next to each line: the original is never modified, and a scene can carry several languages. Lines already translated are not sent back to the model; Force a re-translation makes a new pass. Acting notes (`[ton: …]`, `[pause: …]`) are hidden before translation and restored after: the model cannot translate or invent them. If it loses one, it is displayed under the line. Each request carries the context of the scene, which the model reads without translating: the world (genre, tone, setting, and first the places, factions, and glossary terms that the lines mention), the way the character speaks, where the scene is (location, time, mood), and the preceding lines, in their original words — even when only one line is translated. A precision for the translator is added in the box. An ambiguous word takes on the meaning it has here: isolated, “The col is closed” has become “the gate”; in its scene, “the pass”. World terms keep the same translation everywhere. The first time a scene mentions the world, a place, a faction, or a glossary term, it is translated once and stored in the world, with its language; all subsequent translations in all scenes must use it as is ("King-Cinder" remains "the Ash-King"). A line that forgets it is asked once; what is still missing is signaled under the line. A common word that writes like a term ("naming" the dead, when the glossary has "Name") remains a common word; a term is recognized even when French contracts its article ("

World terms keep the same translation everywhere. The first time a scene mentions the world, a place, a faction, or a glossary term, it is translated once and stored in the world, with its language; all subsequent translations in all scenes must use it as is ("Roi-Cendre" remains "the Ash-King"). A line that forgets it is asked once; what is still missing is signaled under the line. A common word that writes like a term ("naming" the dead, when the glossary has "Name") remains a common word; a term is recognized even when French contracts its article (" In the 'Archives Flottantes' or 'Pont des Brumes'. The lexicon is read and corrected in the 'Mondes' tab › Translation of terms: what you write there is never replaced, and it travels with the world in the exports.
3. Say in English (or the chosen language) on each line of dialogue. The take is kept with the scene (`data/sessions/<personnage>/audio/`) and can be replayed without being redone.

Configure the voice for each language on the character sheet, in the 'Personnages' tab › Voix › Autres langues. For each language, you choose:

- The same voice, keeping the accent — the character speaks English with their French accent. This is what happens for a language that you haven't configured.
- The same voice, native pronunciation — only the tone is taken from the take; the words are pronounced as the model pronounces this language.
- A stable other voice — a real English voice for English. Capture it in the 'Voix' tab with the language of the take: English, describe a native speaker, then Keep it as: their voice only in English. The character's main voice is not affected. An imported recording can also serve.
- An invented or predefined voice, with a specific direction for the language.

Each language can also have its own seed. The 'Voix' tab's test bench has a choice of spoken language: you hear what the sheet will produce without playing the scene, and the line under the choice says which voice will be used.

### To make a character say a whole list of lines: the Lots tab tasks {#faire-dire-toute-une-liste-de-repliques-les-taches-de-l-onglet-lots}

The Lots tab launches tasks. A task makes a character say a whole list of lines — what each line says — and stores everything in its own folder. The lines are not generated one by one: they are generated in batches in a single copy of the voice model, as many as the free graphics memory can hold. A rented high-end card is therefore fully utilized instead of waiting for each line to be generated.

A task can bring its own characters. Task Characters section: add one or more packages exported by PersonaRP (Library › Export and import, Include references). A package contains the complete character: the sheet, their world, and all their stable voices, including those in other languages. They are copied into the task folder, never into your library, and are searched before the library. Uncheck Search also in my library so that a task only speaks with what it brings — this is the case for a rented machine that has nothing else. A voice whose recording no longer matches its fingerprint is excluded and reported, never used as if it were the same.

The list is given in three ways:

- a script, one line per line of dialogue : `Maëlis: Le col est fermé.`, or `COL-01 | Maëlis: Le col est fermé.` to give ID to the line. A line without a name continues the previous line, a line that starts with `#` is a comment, and stage directions (`[ton: …]`, `[pause: 400ms]`) are kept ;
- a CSV (`;` separator, `,` separator or tab) with a header line: `personnage`, `texte`, and optionally `id`, `voix`, `langue`, `fichier`. Without header: character, text, language, file;
- a JSON : a list of objects with the same fields, or `{"lignes": [...]}`.

Each line has a ID : its own, or its number (`0007`) if the list does not give it. Its jack is named this way (`COL-01.wav`) and the ID is in the results. Two lines cannot have the same ID : the second is indicated instead of overwriting the first.

A character is found by their identifier, their name, an alias, or a piece of name that only they bear (« Vasric » finds « Sire Vasric d'Aubrecourt »). If two characters correspond, the line is signaled instead of being given at random to one of them. The column `voix` designates a stable voice, in place of a character or in addition to them. A line without language takes that of the task; a task without language makes each character speak in their own. In another language, it is the voice configuration by language of the sheet that decides: their true English voice for English if they have one, otherwise their voice with their accent.

In the tab:

1. choose the file (Browse) or type the script, then the language, the map, and the lot size — Adapt to the free graphics memory is checked by default
2. add if needed the characters of the task;
3. Check the task: a table says, for each line, its ID, which character speaks and where it comes from (task or library), with which voice and in which language, or why it cannot be said. Nothing is generated and the graphics card is not used: check before paying;
4. Start the task. If a task is already running, the button changes to Put the task in queue: tasks proceed one after another, and the list shows how many are waiting. An impossible replica (unknown character, missing voice) is noted and the rest continues.

Each task has its folder in `data/batches/<nom>-<date>/`:

personnages/          the characters that the task brought: fiches/, mondes/, voix-stables/ (each voice with its recording), import.json source.txt|csv|json   the list as you gave it, intact lot.json              the task as it was understood: each replica, its ID, who says it voix/                 a WAV per replica, named after its ID (COL-01..wav, 0007-….wav) resultats.json        what happened to each replica: ID, text, file, duration, voice and language used, or the error resultats.csv         the same thing, for a spreadsheet

Results are written as they happen. A stopped task resumes (list of tasks, Resume) without redoing the already written replicas, with the characters it brought: on a pay-per-hour machine, nothing is paid twice. Checking what remains shows what the resume will do.

Automatic size is measured, not guessed: a first batch of 4 replicas — the longest, thus the most expensive — measures the real cost of a replica on this card, and following batches are sized according to the remaining memory (up to 32). The worker is limited to the free graphics memory at the start: under Windows, a full card does not return an error but overflows silently in the RAM, which makes everything very slow; with this limit, a too large batch becomes an error, it is split in two and restarted. Replicas of similar length are grouped together to minimize waste.

Measured on a RTX 3090 (24 GB), 16 cloned replicas, about 64 seconds of audio: one by one 76.5 seconds, by 4 26.4 seconds, by 8 16.0 seconds, automatically 15.8 seconds — 4.8 times faster. A cloned replica costs about 1.3 GB during its generation. To measure another card:

A AI connected to MCP sends its list directly, without a file : operation `speak_batch` with `text` (script, CSV or JSON) or `items`, and `dry_run` to check first ; several tasks sent in sequence wait their turn. Everything that is read from the disk — a list in a file or character packets — passes through `speak_batch_file` (`file`, `personas`, `use_library`), reserved like the import to clients who have permission `filesystemExternal`.

### PersonaRP in ComfyUI {#personarp-dans-comfyui}

The Library tab › ComfyUI installs a library of nodes ComfyUI that use the tool: Install here next to your ComfyUI (Comfy Desktop installations are found automatically), or Install in this folder for another, then restart ComfyUI. They are in the category CyTools/PersonaRP:

- Character — the appearance and visual labels, ready for an image prompt;
- Dialogue — the character's response, with image, video, and scene negative prompts, the directive in JSON, audio if the character speaks, and the session to continue;
- Voice — text spoken with the character's voice, in their language or another (the voice configuration by language applies), output in AUDIO from ComfyUI;
- Scene prompts, Translate, Read a photo, Voice task;
- PersonaRP Operation (advanced) — any tool operation, parameters in JSON.

The nodes never import the tool: ComfyUI keeps its Python, PersonaRP its own. They go through the local API of PersonaRP (only on `127.0.0.1`, with a token tucked into `data/settings`, never in a workflow). Opening ComfyUI starts nothing; the first node executed starts PersonaRP, and closing ComfyUI stops it. The progress bar of ComfyUI follows the work, and Stop cancels it. Nodes that use the GPU first unload the models of ComfyUI and then return the memory of PersonaRP (two settings, activated by default). Detailed instructions: `app/comfyui/cytools_personarp/LISEZ-MOI.md`.

### Tasks on Google Colab {#les-taches-sur-google-colab}

To run tasks on a GPU rented, a separate Colab project is created with `runtime/python/Scripts/python.exe app/build_colab.py`: it arrives in `..\CyTools_PersonaRP_Colab`, ready to copy to Google Drive, with its notebook. It contains no models: on Colab, the tool downloads them themselves from the command line, they are recopied and verified on Drive, and the tool then re-reads them from Drive. Results are written to Drive as they are generated, and a cut task resumes where it left off. All is explained in the `LISEZ-MOI.md` of this project.

The tool knows how to read its models and write its tasks elsewhere than in `data/`: environment variables `PERSONARP_MODELS_DIR` and `PERSONARP_BATCHES_DIR` (absolute paths). Tasks also have a precision setting: `auto` uses bfloat16 on cards that can calculate it (RTX 30/40, A100, L4) and float16 on the older ones (T4).

### Engine and Models {#moteur-et-modeles}

The speech engine is private to this tool (about 8 GB) and installs from the Voice tab, like the five variants Qwen3-TTS and Whisper large-v3 turbo. Each capability has its own weights: cloning requires a Base variant, a predefined voice requires CustomVoice, and an invented voice requires VoiceDesign. The tool chooses on its own and warns you if it needs to replace it.

Dictation (under the message field, Scene tab) records the microphone until you stop it (up to 2 minutes), then Whisper transcribes it: the words are added to the message, which you read before sending. The microphone used is the one chosen in the Voice tab (by default, the system's). Since the CLI or MCP, `transcribe` takes a WAV file: no operation opens the microphone, which is recorded only by a button in the window.

## Interface language {#langue-de-l-interface}

The interface is in English by default and fully in French if you choose it in Options. Messages returned by an operation — an error, a note on the used voice, the status of an update — are written once in English, because the CLI and MCP share them; the window displays them translated, values included (e.g.,

## Models {#modeles}

The Models tab shows the installation status, size, bytes already present, license, source, and pinned revision for each model. The license is accepted personally before any download. A download cancels and restarts; nothing is declared installed until its SHA-256 matches. The weights live in `data/models/llm`.

Thirteen models are in the catalog, including two for vision; none are provided with the tool. The model choice, CPU or GPU NVIDIA, is made on the character sheet, Models tab. Speech models have their own list in the Voice tab.

## Updates {#mises-a-jour}

The tool deposit is https://github.com/MrMybal/CyTools_PersonaRP**. It is registered in `app/release.json`, which travels with the application: the Updates tab and the operation `update` use it by default (one can indicate another in the tab). The application, the engine, and the weights are three distinct flows; `data/` is never replaced, a update is verified before being activated at the next launch, and the previous version is kept for going back.

For a update to be visible, the repository must be public (the tool reads GitHub without an identifier) and contain a release whose tag is the version of the tool (`v0.2.0` for version `0.2.0`), with a file `cytools-app.zip` containing the folder `app/`. As long as the repository is private or without a release, it clearly states so on the tab.

## Where are the things {#ou-sont-les-choses}

Nothing is ever deleted by the tool: 'Put in Recycle Bin' moves items to a subfolder `.trash` that you can reopen.
