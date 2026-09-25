# CyTools PersonaRP

Local roleplay with persistent characters, for Windows: a desktop application, a command line
and an MCP server on one runtime, built on the [CyToolsCore](https://github.com/MrMybal/CyToolsCore)
SDK. Characters live in a shared world, remember what you tell them to, speak with a stable
voice, and every reply comes with a machine-readable description of what a camera would see.
French user guide: [LISEZ-MOI.md](LISEZ-MOI.md). Developer guide: [app/README.md](app/README.md).

## What it does

- **Characters**: a complete sheet (identity, appearance, personality, way of speaking, past,
  current state, memory, relationships, voice, visual direction, model settings). Every save is
  a revision; earlier ones are kept and can be restored.
- **Worlds**: shared lore (places, factions, laws, timeline, glossary, what must stay true and
  what never happens). Characters sharing a world know who else lives in it.
- **Relationships** with feeling, trust, shared history, tension and secrets; the reverse link
  can be written on the other sheet automatically.
- **Scenes**: one saved conversation per character, resumed later as it was. Memory is
  explicit: nothing is extracted from a conversation unless you add it.
- **Scene descriptions** for image, video and motion tools, generated alongside each reply.
- **Assistant** that drafts a sheet, a world or one section of either; nothing is applied until
  you accept it. It can start from a **photograph** read by a local vision model
  (Qwen2.5-VL) under constrained decoding.
- **Voice**: Qwen3-TTS (Base, VoiceDesign, CustomVoice), a **stable voice** captured once from a
  12–24 s take and cloned for every later line, acting annotations written by the character,
  Whisper large-v3 turbo transcription.
- **Translation** of a scene with its context (world, character, earlier lines) and a per-world,
  per-language **lexicon** so names of places, factions and things stay the same across
  translations; each language can have its own voice.
- **Voice tasks (batches)**: import complete characters with their stable voices per language,
  give a list of lines (script, CSV or JSON, each with an ID), and get one folder per task with
  every WAV and a results table. Lines are generated several at a time, sized to the free VRAM.
- **Six example worlds**, ready to import, each with three or four characters and their voices.
- **ComfyUI nodes** (`app/comfyui/cytools_personarp`), installed from the application, that use
  the Tool: character, dialogue, voice, scene prompts, translation, reading a photograph, voice
  tasks.
- **Google Colab project** built by `app/build_colab.py`, for voice tasks on a rented GPU: no
  model inside, weights downloaded through the Tool's command line and kept on Drive.
- **Models and engines** installed from the application (state, size, source, licence, pinned
  revision, SHA-256 check, cancel and resume) and **GitHub updates** for the application, the
  engine and the model catalogue, staged, verified and reversible.

The interface is in English by default and fully in French from **Options**.

## Requirements

- Windows 10/11 x64 (the only platform executed by the author; a Linux launcher script is
  provided but was never run), Python 3.11, Git on the PATH.
- An NVIDIA GPU with CUDA for comfortable use; conversation models also run on the CPU. The
  speech engine is about 8 GB on disk.
- Model weights are **not** in this repository; they are downloaded from the Models and Voice
  tabs.

## Installation

```powershell
git clone https://github.com/MrMybal/CyTools_PersonaRP.git
cd CyTools_PersonaRP
# 1. private Python environment of the application (interface, CLI, MCP)
py -3.11 -m venv runtime\python
.\runtime\python\Scripts\python.exe -m pip install -r app\requirements.txt
# 2. Windows launcher (Visual C++ Build Tools)
app\build_launcher.cmd
```

Then double-click `CyTools_PersonaRP.exe`, or run `runtime\python\Scripts\pythonw.exe app\desktop.py`.
On first launch:

1. **Models** tab: install the conversation engine (CUDA or CPU), then at least one
   conversation model.
2. **Voice** tab: install the speech engine, then the speech models you need (1.7B Base for
   stable voices, VoiceDesign to invent a voice, CustomVoice for preset voices, Whisper to
   transcribe takes). The speech engine can also be built with
   `.\runtime\python\Scripts\python.exe app\setup_engine.py voice`.
3. Optional, **Models** tab: a vision model to read character photographs.

## Command line and MCP

```powershell
.\runtime\python\Scripts\python.exe app\tool.py describe
.\runtime\python\Scripts\python.exe app\tool.py list-operations
.\runtime\python\Scripts\python.exe app\tool.py invoke chat --params-file request.json
.\runtime\python\Scripts\python.exe app\tool.py mcp          # MCP stdio server
```

Input paths must be absolute. Operations that download or read files outside the Tool need
the matching permission (`create-client --permission network`, `filesystemExternal`); the
interface has them.

## Repository layout

```
CyTools_PersonaRP.exe   Windows launcher (built locally, not in git)
CyTools_PersonaRP.sh    Linux launcher (never executed by the author)
LISEZ-MOI.md            user guide (French)
app/                    code, manifest (CyTool.json), interface, workers, tests, docs,
                        example worlds, ComfyUI nodes, Colab project sources
data/                   characters, worlds, scenes, voices, models, tasks, jobs, logs (not in git)
runtime/                private Python, engines, staged updates, backups (not in git)
```

Tests (fixtures only, no GPU): `.\runtime\python\Scripts\python.exe -m pip install pytest`, then
`.\runtime\python\Scripts\python.exe -m pytest app\tests -q`.
What was actually executed is recorded in `data/reports/VALIDATION.md` of an installation and
summarised at the end of [LISEZ-MOI.md](LISEZ-MOI.md).

## Licence

Free software under the **GNU General Public License v3.0 only** ([LICENSE](LICENSE)), like the
CyToolsCore SDK it is built on. This covers the code, the interface, the ComfyUI nodes, the Colab
project and the example worlds. Engines and model weights keep their own licences, listed in
[app/licenses.json](app/licenses.json), in the model catalogues and in the Options tab; the
Models tab asks for acceptance before downloading.
