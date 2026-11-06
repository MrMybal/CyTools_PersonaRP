---
id: guide-app-colab-lisez-moi
title: CyTools PersonaRP on Google Colab — voice tasks
description: CyTools PersonaRP on Google Colab — voice tasks
section: Guide
order: 40
parent: guide-lisez-moi
revision: 79685302e5f414f0
---

## CyTools PersonaRP on Google Colab — voice tasks {#cytools-personarp-sur-google-colab-taches-de-voix}

This folder is a separate project, made for Google Colab and stored in your Google Drive. It makes your characters say lists of lines, multiple at once on the rented GPU, and stores everything on Drive. It does not contain any models: the tool downloads them itself via command line on Colab, then they are copied to Drive, where the tool re-reads them for the next sessions.

The SDK CyToolsCore 0.10.1 is public (https://github.com/MrMybal/CyToolsCore, license MIT): the Install step takes it from GitHub, at the commit that the tool fixes in `app/requirements.txt`.

## Setup (one time) {#mise-en-place-une-fois}

1. Copy this entire folder into your Drive, for example `Mon Drive/CyTools_PersonaRP_Colab`.
2. In Drive, open `PersonaRP_Colab.ipynb` with Google Colaboratory.
3. Execution › Modify the execution type: choose a GPU (T4, L4, A100…). The notebook adapts to the card it receives.

## Session workflow {#deroule-d-une-session}

The notebook cells call all `personarp_colab.py` in the command line:

| Step | Command | Indicative duration |
| --- | --- | --- |
| Parameters | project path, models, license, precision | — |
| Drive and GPU | mount Drive, display the map | a few seconds |
| Install | copy the tool to the Colab disk, install its voice engine (PyTorch, Qwen3-TTS) with the tool installer | 3 to 5 minutes, per session |
| Models | `tool.py invoke install_voice_model`: download by the tool (pinned revision, sizes and SHA-256 verified), copy to Drive verified, then delete local copy | the first time only (4.5 GB for the 1.7B Base); then 'already on Drive' |
| Test | une réplique sur cette carte ; choisis la précision (bfloat16 sur A100/L4, float16 sur T4, repli en float32 si la prise n'est pas bonne) | less than a minute |
| Tasks | verify each task without generating anything: who says what, with which voice, which model is missing | a few seconds |
| Run | executes the tasks | according to the list |
| Status | what is installed, on Drive, and does | — |
| Report | `resultats/rapport-colab-<date>.json` : the map, the engine (PyTorch, CUDA), the models on Drive, and the log of each command session (duration, success, last lines displayed). Without token, without model, without voice: this is the file to return for the update. | a few seconds |

Licenses : the models are downloaded only if you have checked `J_ACCEPTE_LES_LICENCES` after reading the displayed license (Qwen3-TTS : Apache-2.0, model page on Hugging Face).

## A task {#une-tache}

A task is a dossier in `taches/`:

taches/ ma-scene/ liste.csv            the list of lines (or .txt, .json) — one per character folder characters/         the characters exported by PersonaRP, with their recordings valdrenn.zip tache.json           optional: the task settings

Characters export from PersonaRP to your PC : Library › Export and import, check Include reference records. The package contains the card, the world and all stable voices, including those of other languages. Colab has no library: a task speaks only with the characters it brings.

The list has the formats of the Lots tab in PersonaRP:

- CSV : `id;personnage;texte;langue` (the `id` calls it : `SC01-05.wav`) ;
- script : `SC01-05 | Maëlis: [ton: bas] Le col est fermé.` — one line per line of dialogue ;
- JSON : `[{"id": "SC01-05", "personnage": "Maëlis", "texte": "…", "langue": "English"}]`.

`tache.json` (all is optional) :

nom: ma-scene, langue: , taille_lot: 0, graine: 42, precision: , bibliotheque: false, appareil: cuda

`langue` empty : each character in its own. `taille_lot` 0 : size measured on the map. `precision` empty : that chosen by the trial.

## The results {#les-resultats}

Each task writes to `resultats/<nom>-<date>/`, step by step:

personnages/     the characters that the task has brought source.csv       the list as given lot.json         the task as understood voix/            one WAV per line, named according to its ID resultats.json   for each line: ID, text, file, duration, voice and language, or error resultats.csv    the same for a spreadsheet

`resultats/_taches.json` keeps track of what has been done. If the Colab session stops or if you interrupt the cell, simply relaunch Launch: the task resumes from where it left off, without redoing what is already written on Drive. A completed task is not redone; to redo it, remove its line from `_taches.json`.

## Multiple lines at once {#plusieurs-repliques-a-la-fois}

The lines are generated in batches in a single copy of the model. The first batch of 4 measures the cost of a line on the map, the following batches are sized according to the available memory. On a RTX 3090 (24 GB), 16 cloned lines: 74.7 seconds one by one, 15.7 seconds in automatic batches. A cloned line costs about 1.3 GB during its generation.

## What has been verified, and what has not been verified {#ce-qui-a-ete-verifie-et-ce-qui-ne-l-a-pas-ete}

Verified on Windows (RTX 3090), on September 25, 2026:

- the creation of this folder, without any model files;
- the tool that starts without a graphical interface or audio library;
- `installer` (code copy, light installation), `etat`, `taches`: the example task signals the missing model and says which `--modele` to add; then, the tool reads its models from another folder as it will do on Drive, and the 10 replicas are ready;
- `modeles` without license agreement: the tool refuses any download before, displays the license and its source, and the client token does not appear on the screen or in the project;
- the verified copy of the models (size and SHA-256, a damaged copy is detected);
- the addresses and sizes of the 66 voice files in the catalog on Hugging Face;
- a replica in float16, the precision of a T4: Whisper finds the exact phrase, just like in bfloat16.

Nothing has yet run on Colab itself: neither the installation of the engine under Linux, nor the complete download of a model by the tool, nor a task on T4, L4, or A100. The first session is therefore also a test; each step clearly indicates what is not working.
