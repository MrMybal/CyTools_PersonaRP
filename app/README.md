# CyTools_PersonaRP — developer documentation

`cy.tool.personarp`, built on CyToolsCore 0.9.0. Local roleplay with persistent characters,
a shared world, relationships, and machine-readable scene descriptions for image and video
tools. No model is part of the repository: engines and weights are downloaded from the
interface (Models tab, Voice tab), each at a pinned revision and verified by SHA-256.

License: GPL-3.0-only (`../LICENSE`), like the CyToolsCore SDK it is built on. It covers the
code, the window, the ComfyUI node pack (which carries its own copy of the licence), the Colab
project and the example worlds; model weights are downloaded separately under their own
licences (`licenses.json`, `llm-catalog.json`, `tts-catalog.json`).

## Install, build, run

```
py -3.11 -m venv runtime/python
cd app && ../runtime/python/Scripts/python.exe -m pip install -r requirements.txt
```

The requirement file installs CyToolsCore 0.9.0 (GPL-3.0-only) from its public repository,
https://github.com/MrMybal/CyToolsCore, pinned to commit `442f53740fc6` — the code this Tool was
verified against (the published files match the wheel it was developed with, line endings and
one trailing blank line aside). **git must be on the PATH**: pip clones that commit.

| Task | Command |
| --- | --- |
| Regenerate the manifest | `runtime/python/Scripts/python.exe app/build_manifest.py` |
| Tests (no model) | `runtime/python/Scripts/python.exe -m pytest app/tests -q` |
| Real MCP session | `runtime/python/Scripts/python.exe app/tests/acceptance_mcp.py` |
| Real speech acceptance | `runtime/python/Scripts/python.exe app/tests/acceptance_voice.py` |
| Voices of the example characters (GPU, resumable) | `runtime/python/Scripts/python.exe app/build_example_voices.py [01-valdrenn ...]` |
| Play two example worlds with the real model | `runtime/python/Scripts/python.exe app/tests/acceptance_examples.py` |
| Real translation + voices per language | `runtime/python/Scripts/python.exe app/tests/acceptance_translation.py [llm-model]` |
| The terms of a world kept across translations (about 1 min of GPU) | `runtime/python/Scripts/python.exe app/tests/acceptance_translation_terms.py [llm-model]` |
| Translation with and without the scene's context (about 1 min of GPU) | `runtime/python/Scripts/python.exe app/tests/acceptance_translation_context.py [llm-model ...]` |
| Voice batches: sequential vs batched on the real model (about 3 min of GPU) | `runtime/python/Scripts/python.exe app/tests/acceptance_batch.py [--lines 8] [--check-only]` |
| Build the Colab project (no model) | `runtime/python/Scripts/python.exe app/build_colab.py` |
| Build the Windows release (portable zip, cytools-app.zip, SHA256SUMS.txt) | `runtime/python/Scripts/python.exe app/build_release.py` |
| Run the release as a user would (extracted copy, bare environment) | `runtime/python/Scripts/python.exe app/tests/acceptance_release.py [zip] [--tests] [--keep]` |
| Every tab of the window | `runtime/python/Scripts/python.exe app/tests/smoke_ui.py` |
| Every tab, in French | `runtime/python/Scripts/python.exe app/tests/smoke_ui.py --language fr` |
| French strings the catalogue lacks | `runtime/python/Scripts/python.exe app/tests/locale_strings.py` |
| Build the voice engine | `runtime/python/Scripts/python.exe app/setup_engine.py voice` |
| Rebuild the voice catalogue | `runtime/python/Scripts/python.exe app/build_tts_catalog.py` |
| Window, one tab, screenshot | `runtime/python/Scripts/python.exe app/desktop.py --smoke-tab Scene --strict-ui` |
| Build the Windows launcher | `app/build_launcher.cmd` (needs the Visual C++ toolchain) |
| One reply from the CLI | `runtime/python/Scripts/python.exe app/tool.py invoke chat --params-file p.json` |

`CyTool.json` is **generated** from `personarp/schemas.py` by `build_manifest.py`. Never edit
it by hand: a test compares the published manifest with the generator's output, because a
stale manifest silently rejects valid documents through output validation.

## Layout

```
app/
  tool.py                 Runtime and every operation handler
  desktop.py              Dear ImGui window
  build_manifest.py       generates CyTool.json from the schemas
  llm-catalog.json        conversation models: repo, pinned revision, size, SHA-256, licence
  personarp/
    paths.py              folders, atomic JSON read/write
    schemas.py            persona, world, relation, scene, voice — the portable contract
    library.py            collections, revisions, trash, relationships, export/import
    batches.py            voice batches: parsing, speaker lookup, folders, results
    sessions.py           saved conversations
    prompting.py          prompt assembly, context budget, director prompt
    scene.py              reply parsing, annotations, directive schema and sanitising
    authoring.py          the creation assistant
    models.py             catalogue, installation state, download, engine paths
    resident.py           the owned llama.cpp server
    context_window.py     tokenizer-based history fitting
    derived.py            writing-style output head applied to a private copy of a base model
    maintenance.py        GitHub updates: stage, verify, activate, roll back
    locks.py              cross-process locks
    marks.py              the delivery-mark vocabulary, standard library only
    workerhost.py         persistent worker processes over JSON lines
    voice/
      catalog.py          speech models and the private engine
      annotations.py      marks compiled into a plan of passages and silences
      stable.py           stable voices: create, verify, lock, trash
      delivery.py         which voice, which mode, which weights, which instruction
      runner.py           the worker pool bound to the runtime
      batching.py         batch sizing and out-of-memory backoff, standard library only
  workers/                _protocol.py, tts_worker.py, stt_worker.py — run in the voice engine
  gui/                    state.py, widgets.py, panels.py, voice_panel.py, batch_panel.py, player.py
  tests/                  pytest suite, MCP acceptance, speech and batch acceptance
  examples/lots/          example batches (script, CSV, JSON) for the Valdrenn cast
```

## Two environments

`runtime/python` is the Tool's own light environment: the SDK, Dear ImGui, soundfile. The
speech stack lives apart in `runtime/engines/voice` (PyTorch CUDA, Qwen3-TTS, Whisper, about
8 GB), built by `app/setup_engine.py` at its final path and never moved. Nothing heavy is
imported by the window, the CLI or the MCP server: the workers in `app/workers` run inside
the engine and talk over the JSON-lines protocol in `personarp/workerhost.py`.

The workers import `personarp.voice.annotations` and nothing else of ours, which is why the
mark vocabulary sits in `personarp/marks.py` on the standard library alone — the SDK is not
installed in the engine.

### The binary release

`app/build_release.py` builds the release from the commit HEAD (`git archive`; uncommitted
changes are refused) into `runtime/build/release/<version>/`. In the portable zip,
`runtime/python` is not a virtual environment but a private CPython 3.11, copied from an
official installation without site-packages, byte-code, Tk, IDLE or the test suite. Its
interpreter and the DLLs it loads live in `runtime/python/Scripts`, so every path the Tool
already uses (the launcher, the manifest's `executable`, the ComfyUI nodes, the voice engine
setup) finds it where a virtual environment would put it; Python finds `Lib/` by searching
upwards from the executable. `runtime/python/pyvenv.cfg` holds only
`include-system-site-packages = false`: with no `home` line the interpreter keeps its own
folder as prefix, and `site` (frozen into the 3.11 executable, so editing `Lib/site.py` would
change nothing) turns the per-user site-packages off, so a user's own packages never shadow the
Tool's. Packages are installed at the versions of the development runtime (constraints from its
`pip freeze`), console-script wrappers (which hold the absolute path of the build machine) and
every `__pycache__` are removed, `runtime/python/THIRD-PARTY.md` lists each package and its
licence, and `runtime/build-info.json` records the commit and the versions. The build fails if
the packaged interpreter reads anything outside the package, or if any file of the package names
the project folder, the base Python, the user profile (long or 8.3 form) or the machine name.
The voice engine is created from this interpreter with `venv`, which the copy keeps.

`app/tests/acceptance_release.py` extracts the zip into a new folder with a space in its name
and runs it with PATH reduced to Windows, no `PYTHON*` variable and a working directory outside
the package: layout, interpreter isolation (including a module planted in a per-user
site-packages, which must stay invisible while the machine's own CPython, the control, imports
it), the CLI, a real MCP session whose client is granted `filesystemExternal` and imports an
example world, the launcher opening two tabs, a `venv` made from the private interpreter, and
with `--tests` the whole suite inside the copy.

## Voice

A capability is a set of weights, not a flag. Qwen3-TTS ships one variant per capability and
refuses the others outright, so `delivery.VARIANTS` maps the mode to the weights and
`_model_for` substitutes with an explanation rather than letting the model answer with a
message about tokenizer types:

| Mode | Weights | Used when |
| --- | --- | --- |
| `clone` | `1.7B-Base`, `0.6B-Base` | a stable voice is attached — the normal case |
| `design` | `1.7B-VoiceDesign` | the sheet carries a written voice description |
| `custom` | `1.7B-CustomVoice`, `0.6B-CustomVoice` | a preset speaker |

A stable voice is a document in `data/voices` holding the reference recording, its exact
transcript, its SHA-256 and the variant that reads it. It is locked on creation: changing the
reference or the model is refused, because a voice that quietly changes is worse than no
voice. `verify_voice` reports a moved or modified recording.

The take produced by `capture_voice_take` is copied to `data/voices/takes` before the job
workspace disappears, so it can still be registered later.

`spoken_text` decides what reaches the worker: the scene directive never does, narration does
only when the sheet says so, and annotations are kept only for a backend that understands
them.

`generate_voice_clone` has no instruction input, so in `clone` mode the acting direction and
the tone marks are built but not read by the model; only pauses (rendered as silence by the
plan) reach a cloned voice. The sheet says so next to the stable voice picker.

### Languages

`voice.language` on the sheet is the character's own language and wins over the language
recorded on the stable voice (`delivery.native_language`). `voice.languages[]` holds one entry
per other language (`LANGUAGE_VOICE_SCHEMA`), and `payload_for(..., language=)` applies it:

| `source` | What speaks | Mode |
| --- | --- | --- |
| `same`, `accent: keep` (also: no entry) | the main voice; the in-context clone carries the take's accent | `clone`, full reference |
| `same`, `accent: native` | the main voice's timbre only | `clone`, `x_vector_only` |
| `voice` | another stable voice, typically captured in that language | `clone` |
| `design` | a voice invented from the entry's description | `design` |
| `preset` | a preset speaker with the entry's direction | `custom` |

Without a stable voice, `same` asks for the accent in the instruction instead. A missing
per-language voice falls back to the main voice with a note, never silently. The payload's
`voice_plan` (returned as `voicePlan`) says what was really used.

Every translation request carries `translation.context_block()` — the world (genre, tone,
summary, setting; places, factions and glossary terms, those the batch mentions first), who
speaks and how (personality, speech style, register, vocabulary, accent, tics), the sheet's
current state (situation, place, time, mood), the session title and the caller's `context`
note — bounded to 3 000 characters, and `translation.earlier_lines()`: the four turns before
the batch in their original words, with their translation when one exists or was just made.
The system prompt says the context is for understanding only. A `text` given with a
`session_id` is translated with that scene as context and nothing is stored; `world_id` gives
a text without a character its world. Measured with `tests/acceptance_translation_context.py`.

**The lexicon.** `world.term_translations[<Language>][<term>] = {text, source: model|person,
model, at}`. `translation.world_terms()` lists the glossary terms, locations and factions;
`mentioned_terms()` finds them in a text (accent- and case-folded, whole words, a plural s/x
allowed). Terms mentioned but not yet rendered go through one constrained pass
(`terms_messages`, `terms_schema` — the meaning is a hint, a rendering is bounded to a name's
length) and `parse_terms` keeps only plausible names (no sentence, a leading article
lower-cased); they are recorded in the world unless `keep_terms` is off. Each batch then gets
the renderings of the terms it uses as names (`used_as_name`: a compound always, a single word
only where it is capitalised), `missed_terms` checks the answer (article dropped, plural and
possessive allowed), a line that dropped one is asked again once with `insist`, and what is
still missing is stored as `termsMissed` on the turn. `save_world` keeps the lexicon on disk
(a window's older copy cannot wipe it); it changes through `translate` and
`set_term_translations` only (`source: person` is never replaced), and `translation_terms`
reads it. A first version of the terms prompt presented the meaning beside the term and a 4B
model translated the meaning; `tests/acceptance_translation_terms.py` now fails on a
description-like rendering.

`translate` (see `personarp/translation.py`) masks the delivery marks as `⟦n⟧` tokens,
batches turns up to 2 400 characters, constrains the answer to one non-empty string per turn,
restores the marks and reports any the model lost. Translations are stored beside the turn
(`turn.translations[<Language>] = {text, model, at, marksLost, audio?}`); the original is never
rewritten, already translated turns are skipped unless `overwrite`, and a changed translation
drops the take made from the old words. `speak_turn` speaks a stored line in its own language
or a translation and keeps the take under `data/sessions/<persona>/audio/<session>/`.
`create_stable_voice` with `for_language` attaches a voice to that language only;
`capture_voice_take` ignores the per-language entries so a take is always the voice described.

### Batch tasks

`speak_batch` (list inline: `text` as a script, CSV or JSON — `format` auto-detects — or
`items`, or `resume`) and `speak_batch_file` (anything read from disk: `file`, `personas`,
`use_library`; `filesystemExternal`) share one handler. The split exists because permissions
are per operation: an AI client with no permission must be able to send its lines, while
reading an arbitrary file stays reserved, like `import_personas`. `list_batches` lists
`data/batches`. Tasks are ordinary jobs: several submitted in a row wait behind the runtime's
`Sequential` policy, and the window queues them in `App.pending`.

**A task's own characters.** `personas` are bundles exported by `export_personas` with the
recordings. `batches.import_task_personas` copies them into `<task>/personnages/` (`fiches/`,
`mondes/`, `voix-stables/` with each recording and a relative path, `import.json`) and never
into the library; within the task a taken identifier gets a new one and the sheets follow it.
A voice without its recording, or whose recording does not match `reference_sha256`, is
refused and listed in `problems`. `batches.load_task` reads them back — on every run, resume
included — and checks each recording against its fingerprint again. `delivery.payload_for`
takes these voices as `voices=`; `_stable` looks there before the library. `Cast` searches the
task's sheets first, then the library unless `use_library` is off; the source of each speaker
(`task`, `library`, `voice`) is recorded on the line so a resume speaks with the same one.
`library.voice_ids` / `_voice_documents` export the per-language voices as well as the main
one — before, an exported character lost its English voice.

**Line ids.** `batches.assign_ids` gives every line its own id (CSV `id` column, JSON `id`,
script `ID | Name: text`) or its number; a repeated id (case-insensitive, as on Windows) is
reported on the second line instead of overwriting the first take. `file_stem` names the take
after the id (`safe_name` keeps `SC01_L005` as it is, reserved device names are prefixed).

The handler (`tool.py`, `_speak_batch`) parses (`personarp/batches.py`), finds each speaker
(identifier, name, alias, then a run of whole words only one name holds — an ambiguous name is
an error, never a guess), builds each line's payload with `delivery.payload_for` exactly as
`speak` does, and groups the lines by `(mode, model)`: one worker request per set of weights.
`dry_run` stops there and returns the plan; it imports the task's characters into the job's
own workspace, makes no task folder, takes no lock and reserves no VRAM.

The worker (`synthesize_batch` in `workers/tts_worker.py`) loads the weights once, cuts every
line into its plan, pools the passages of all lines longest first
(`personarp/voice/batching.py`) and calls `generate_voice_clone` / `generate_voice_design` /
`generate_custom_voice` with lists — Qwen3-TTS batches them in one forward pass, each with its
own voice prompt, language and instruction. One clone prompt is encoded per reference, however
many lines use it. `batch_size` 0 measures instead of guessing: a first batch of
`PROBE_BATCH` (4) passages — the longest, so the dearest — gives the cost of one passage
(`max_memory_allocated` above the weights), and `fit` sizes the next batches from the room left
(`SAFETY` 0.85, 32 at most). The worker caps its allocator with
`set_per_process_memory_fraction` at what was free when it started, minus 1.5 GiB: on Windows
the driver otherwise spills into system memory instead of failing — a first version asked for
26 GB on a 24 GB card and ran 3.7 times slower than one line at a time. Under the cap an
oversized batch raises out-of-memory, is halved and retried, and never grows again
(`generate_all`). The cap is lifted after the batch so single takes are not limited.
Measured on an RTX 3090, 16 cloned lines: size 1 76.5 s, 4 26.4 s, 8 16.0 s, automatic 15.8 s;
about 1.3 GB per cloned passage (`tests/benchmark_batch.py`). The takes are
reassembled per line with `render_plan`, silences included. One seed per request: a batch does
not reproduce the per-line seeds of `speak`, so a voice that must stay the same across lines
should be a stable voice.

Results are written after every group (`resultats.json`, `resultats.csv`), so an interrupted
task keeps what it finished; `resume` skips every line marked `ok` whose WAV still exists and
looks the others up again (a character created since is found). The global execution lock
still holds: a task is one job, and the parallelism is inside the model's batch, not across
processes.

### ComfyUI

`app/comfyui/cytools_personarp` is a ComfyUI node pack; `personarp/comfyui.py` installs it
(`install_comfyui_nodes`, `filesystemExternal`) into the `custom_nodes` of a ComfyUI given as
its folder, a base directory or `custom_nodes` itself, and finds Comfy Desktop installations
from `installations.json` (`adoptedBaseDir`, `basePath`, `installPath`). The copy is staged and
swapped in whole; `config.json` names the Tool; `comfyui_nodes_status` compares the digest of
the files really installed with the source.

The pack never imports the Tool (a test forbids it): `client.py`, standard library only, speaks
the CyTools protocol to `tool.py --data-dir data/jobs-comfyui serve --port 8791` — its own job
store, since two runtimes cannot own one — with a token from `tool.py create-client`
(filesystemExternal, network) kept in `data/settings/comfyui-client.json`. It starts the
server on the first node that runs, never on a menu (menus read `data/personas`,
`data/voices` and the catalogues while the server is down), probes it with `GetCapabilities`,
never starts a second one, and stops it at exit with the whole process tree — on Windows the
venv's python.exe is a launcher whose child is the real server. Jobs follow ComfyUI's progress
bar; ComfyUI's interruption cancels them. GPU nodes can `unload_all_models()` first and call
`unload_model` / `release_voice` after. AUDIO is `{'waveform': [1, C, T], 'sample_rate'}`;
takes are copied into ComfyUI's `output/personarp`.

`GetRuntimeStatus` answers `InternalError` in CyToolsCore 0.9.0 — an SDK defect, worked around.

### Colab

`app/build_colab.py` builds `CyTools_PersonaRP_Colab` beside the Tool: `outil/app` (the Tool
without `gui/`, `desktop.py`, the UI helpers, `tests/`, `Docs/`, `locales/`),
`outil/packages` (the CyToolsCore wheel), the runner `app/colab/personarp_colab.py`, a notebook
generated by the build script (one source), `app/colab/LISEZ-MOI.md` and an example task. It
refuses to build if a weight file slipped in, and rebuilding leaves `taches/`, `modeles/` and
`resultats/` alone.

The runner copies the Tool to the Colab disk, installs it and runs `setup_engine.py voice`
(falling back to `virtualenv` where `venv` has no `ensurepip`). `modeles` downloads with the
Tool's own CLI — `tool.py create-client` (network, filesystemExternal; the token is kept on
the Colab disk and passed as `CYTOOLS_TOKEN`, never in argv or on Drive) then
`tool.py invoke install_voice_model` — copies the model to Drive through `.part` files,
verifies size and SHA-256 there and drops the local copy. Every other command runs the Runtime
in process with `PERSONARP_MODELS_DIR` and `PERSONARP_BATCHES_DIR` on Drive (`paths._location`
accepts absolute paths only). `essai` speaks one line and keeps the first precision whose take
is usable (auto, then float32). `lancer` records `resultats/_taches.json` so a new session
resumes an interrupted task with `speak_batch resume`.

`precision` (`auto`, `bfloat16`, `float16`, `float32`) reaches the worker, which resolves auto
from the compute capability (bfloat16 from 8.0, float16 below, float32 on the CPU) and keys the
resident model by dtype.

## Photographs and the vision pass

A sheet carries `references[]`: photographs copied into `data/personas/<id>.images`, each
with its role, caption, pixel size and SHA-256. `imaging.verify` reports a picture that has
moved or changed. They are export material and vision input; `prompting` never puts them in
front of the roleplay model.

`describe_image` reads one downscaled picture (long edge 1024, JPEG) in two passes on the same
resident vision model:

- **look** — the picture with `authoring.observation_request()`, no grammar: 150 to 300 words
  of English prose, garment by garment. A single pass constrained to JSON answered one word
  per field (« longue », « bleus »): the grammar let the model stop as soon as a field was
  technically filled. The observation is returned as `observation`.
- **write** — text only, `authoring.vision_request(..., observation=)` under
  `authoring.vision_schema()`: every field required but allowed empty (optional fields were
  skipped although the observation described them), a minimum length on summary, hair, eyes
  and outfit, six to twelve tags of at least twelve characters with a good and a bad list
  (« jeune femme », « yeux bleus » are true of thousands of people), one language only.
  `authoring.clean_vision_fields` then removes CJK characters from a sheet in another
  language (Qwen drifts into Chinese now and then), stuttered words and repeated tags.

The assistant's picture context gets both the fields and the observation.

The result is a proposal applied through `apply_proposal`, so a photograph can never
overwrite a branch you did not ask it to.

`resident.ensure` passes `--mmproj` when the catalogue entry declares one, and
`--no-mmproj-auto` otherwise so llama-server never fetches a projector by itself. The
projector path is part of the resident key, and the history-fitting pass is skipped for a
multimodal call because re-templating a message that carries an image does not survive.

## The data model

A **persona** is one JSON document validated by `PERSONA_SCHEMA`. Branches: `appearance`,
`personality`, `speech`, `background`, `state`, `memory`, `relationships`, `voice`, `media`,
`generation`. `state` and `memory` are the parts meant to change as a story advances;
everything else is the character.

A **world** is a separate document holding the lore several personas share. A persona points
at one through `world_id`. `library.cast(world_id)` returns the others, which the prompt
mentions so a character does not invent people who already exist.

Every `save` writes a new revision and archives the previous document under
`<id>.revisions/`. `remove` moves to `.trash`. Nothing is ever deleted by an operation.

Identifiers are readable slugs (`nymphaea`), validated against `[a-z0-9][a-z0-9-]{0,79}`;
anything else is refused before it can reach the filesystem.

## Prompt assembly

`prompting.messages()` builds the system prompt in priority order and drops the least
essential sections when the character's `context_budget` is exceeded. The identity section
is never dropped. What was dropped is returned in `context.droppedSections`, so the
interface can say so instead of degrading the character silently. A second, tokenizer-based
pass (`context_window.fit_messages`) then fits the real model context once the server is up.

Past assistant turns are cleaned before they go back into the prompt: the scene directive is
removed and the delivery annotations are stripped. Leaving the directive in would teach the
model to answer in JSON.

## The scene directive

Two modes, on `media.mode`:

- **`director`** (default) — the roleplay model writes only the reply. A second call, with
  `json_schema` set from `scene.director_schema()`, asks a storyboard prompt for the shot.
  llama.cpp compiles that schema into a decoding grammar, so the JSON is always parseable.
  The directive is then run through `scene.sanitize_directive()`, which clamps ranges a
  grammar cannot express (a negative timestamp, a 900-second clip) instead of discarding a
  whole description over one bad float.
- **`inline`** — the instruction is appended to the roleplay prompt and the reply is parsed
  with `scene.split_reply()`. One generation instead of two, but small models often skip it.

The director prompt receives only visual facts. Memory, secrets and the conversation history
are deliberately excluded: they are not what a camera sees.

`media.director_model` selects a different installed model for the description pass. The
first pass is forced to `keep_loaded` while a director pass follows, and the caller's real
preference is applied once, afterwards.

## Voice annotations

`[tone: …]`, `[ton: …]`, `[pause: 400ms]`, `[émotion: …]`, `[rate: …]`, `[volume: …]`,
`[murmure]` and their English spellings map to one canonical kind in `scene.KINDS`. Unknown
brackets are left alone, so ordinary prose in square brackets survives. `scene.tidy()` closes
the gap a removed mark leaves, because "Bonjour ." is an audible pause in a speech backend.

## Example worlds

`app/examples/NN-<world>.zip` are ordinary export bundles — one world, its cast and one locked
stable voice per character with its reference recording —
listed by `list_examples` (`personarp/examples.py`) and imported with `import_personas`. They
ship with the application rather than in `data/` because an import is a copy. `import_bundle`
remaps the bonds between characters imported together when one of them has to take a new
identifier, so importing an example twice gives two casts that point at themselves.
`tests/test_examples.py` validates every bundle against the schemas, checks every bond
target, imports each twice, and runs each sheet through `prompting.messages` — the chat's own
path, which gives the sheet 70 % of `context_budget` — to prove nothing is dropped;
`tests/acceptance_examples.py` plays two of them with the real model in a temporary library.
`build_example_voices.py` produces those voices: a take per character invented by VoiceDesign
from the sheet's voice description and the character's own words, transcribed back by
Whisper and recaptured with another seed below 80 % of the words heard, registered as a
stable voice and re-exported with the recording. It works in `runtime/build/example-voices`,
never in `data/`, and skips a character that already has its voice, so it can be stopped and
resumed. `--takes <folder>` takes ready-made `<persona-id>.wav` + `.txt` instead (no GPU).

Importing a voice never touches one already in the library: the same recording (same
SHA-256) is reused, a different voice under the same name comes in as `<id>-2`, and the
imported sheets follow the new identifier.

Optional object parameters (an inline sheet, a mirror bond, a voice override) carry no
default in the manifest: the validator would expand `{}` into a complete blank document that
then replaces the real one. `optional()` and `partial()` in `build_manifest.py` build them,
and a test forbids a defaulted optional object.

## Interface languages

English is the default; French is chosen in Options. Every string the window shows is looked
up in `app/locales/ui.json`. `tests/locale_strings.py` reads the window's code the way it
translates it — facade labels, shared widgets, `tr()`, notices, loop captions, `*_CAPTIONS`
constants and the progress steps jobs report — and `tests/test_locale.py` fails when a string
has no French, when a label is formatted or concatenated before translation (no entry could
match it), or when a French string changes on a second translation. Translate a template
before formatting it: `tr('Take of %.1f s ready.') % seconds`, never the formatted result.

## What this build does not do

No microphone capture (dictation works on a WAV through `transcribe`), no Linux runtime, no
CPU-only speech run, and no update against a published GitHub release.
The acceptance runs write their evidence to `data/reports/` (local, never committed);
`VALIDATION.md` there is the authority on what has actually been executed; it also
lists the five defects the acceptance runs found and the fixes they produced.

## Contracts followed

`Docs/StandaloneDelivery.md` (clean root, real ImGui window, guided model installation,
GitHub updates with rollback), `Docs/SharedInstallation.md` (private Python, no automatic
model relocation — the migration here was an explicit, receipted, reversible action),
`Docs/Localization.md` (English by default, French selectable, Options tab from the SDK),
`Docs/GenerationConfigurations.md` (save/load the current configuration).
