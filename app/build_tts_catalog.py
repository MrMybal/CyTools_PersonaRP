"""Build app/tts-catalog.json from the source.json manifests that came with the weights.

The manifests are path-independent records of what was downloaded (repository, pinned
revision, every file with its size and, where the hub published one, its SHA-256). Turning
them into the Tool's own catalogue means a fresh machine can download exactly the same
files, and this machine can verify what it already has.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TTS = ROOT / 'data/models/tts/qwen3tts'
STT = ROOT / 'data/models/stt'

LABELS = {
    '1.7B-CustomVoice': ('Qwen3-TTS 1.7B CustomVoice', 'tts', 8, 6,
                         'Preset speakers steered by a written instruction. It cannot clone a '
                         'recording: stable voices run on a Base variant.'),
    '1.7B-VoiceDesign': ('Qwen3-TTS 1.7B VoiceDesign', 'tts', 8, 6,
                         'Invents a voice from a written description, with no recording. Useful '
                         'to produce the first take of a character that has never been heard.'),
    '0.6B-CustomVoice': ('Qwen3-TTS 0.6B CustomVoice', 'tts', 5, 3,
                         'Lighter and faster than the 1.7B, with a plainer delivery.'),
    '1.7B-Base': ('Qwen3-TTS 1.7B Base', 'tts', 8, 6,
                  'The variant that clones: it is what a stable voice actually runs on. '
                  'CustomVoice and VoiceDesign cannot clone a reference.'),
    '0.6B-Base': ('Qwen3-TTS 0.6B Base', 'tts', 5, 3,
                  'Lighter cloning variant, faster and less faithful to the reference.'),
}

catalog = {}
for folder in sorted(TTS.iterdir()) if TTS.is_dir() else []:
    source = folder / 'source.json'
    if not source.is_file():
        continue
    document = json.loads(source.read_text('utf-8'))
    name, kind, ram, vram, notes = LABELS.get(
        folder.name, (folder.name, 'tts', 8, 6, ''))
    catalog['qwen3tts-' + folder.name.lower()] = {
        'name': name, 'backend': 'qwen3tts', 'variant': folder.name, 'kind': kind,
        'directory': 'tts/qwen3tts/' + folder.name,
        'repo': document['repository'], 'revision': document['revision'],
        'page': 'https://huggingface.co/' + document['repository'],
        'license': document.get('license', 'Apache-2.0'),
        'files': [{'name': item['path'], 'size': item['size'], 'sha256': item.get('sha256') or ''}
                  for item in document['files']],
        'ramGiB': ram, 'vramGiB': vram, 'notes': notes,
    }

# Whisper came without a folder-level manifest, so rebuild one from the per-file receipts:
# each records the exact URL it was fetched from, its size and its verified digest.
whisper_dir = STT / 'whisper-large-v3-turbo'
receipts = sorted(whisper_dir.glob('*.installed.json')) if whisper_dir.is_dir() else []
if receipts:
    files, repo, revision = [], '', ''
    for receipt in receipts:
        record = json.loads(receipt.read_text('utf-8'))
        url = record.get('url', '')
        if '/resolve/' in url:
            repo = url.split('https://huggingface.co/', 1)[-1].split('/resolve/')[0]
            revision = url.split('/resolve/', 1)[1].split('/', 1)[0]
        files.append({'name': receipt.name[:-len('.installed.json')],
                      'size': record.get('actualSize') or record.get('size', 0),
                      'sha256': record.get('actualSha256') or record.get('sha256') or ''})
    catalog['whisper-large-v3-turbo'] = {
        'name': 'Whisper large-v3 turbo', 'backend': 'whisper',
        'variant': 'large-v3-turbo', 'kind': 'stt',
        'directory': 'stt/whisper-large-v3-turbo',
        'repo': repo, 'revision': revision,
        'page': 'https://huggingface.co/' + repo,
        'license': 'MIT',
        'files': files,
        'ramGiB': 4, 'vramGiB': 3,
        'notes': 'Transcribes a reference recording so a cloned voice knows exactly what was '
                 'said, and transcribes dictation.',
    }

target = ROOT / 'app/tts-catalog.json'
target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
for key, entry in catalog.items():
    total = sum(f['size'] for f in entry['files'])
    hashed = sum(1 for f in entry['files'] if f['sha256'])
    print('%-28s %6.2f GB  %2d files (%d hashed)  %s'
          % (key, total / 1e9, len(entry['files']), hashed, entry['revision'][:12]))
print('written:', target)
