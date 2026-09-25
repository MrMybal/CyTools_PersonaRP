"""Real acceptance of the batch tasks, on the real voice model. Nothing touches your library.

Two temporary libraries stand for two machines.

  The machine that prepares: the Valdrenn example is imported, Maëlis gets a real English
  stable voice (designed, transcribed by Whisper, attached to English only), two characters
  are added that speak with an invented voice and a preset speaker, and all six are exported
  with their recordings — one bundle.

  The machine that runs, whose library is empty: every task brings that bundle and is told
  not to look in the library.
    1. a check: every line must be ready, Maëlis's English lines on her English voice;
    2. the same lines one passage at a time (batch_size 1), then sized to the free VRAM
       (batch_size 0): every take must exist under its id, last long enough, not be silent;
    3. the invented voice and the preset speaker in a batch of their own;
    4. the batched task resumed: nothing generated again;
    5. Whisper transcribes takes of the batched run and of the modes: each must say its own
       line — a batch that mixed up its outputs would fail here.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_batch.py [--check-only]
Writes data/reports/batch-acceptance.json and copies a few takes to data/reports/audio/lots/.
About five minutes of GPU on an RTX 3090; the automatic batch takes whatever VRAM is free.
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
import time
import unicodedata
import wave
from array import array
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from personarp import batches, library, sessions                      # noqa: E402
from personarp.paths import DATA                                       # noqa: E402
from personarp.schemas import FORMAT_PERSONA, normalize_persona, normalize_world  # noqa: E402
from personarp.voice import stable                                     # noqa: E402

ENGLISH_VOICE = ('A young woman from the north of England, low and steady, a little husky, '
                 'who speaks slowly and does not raise her voice.')
# (id, character, text, language) — the stable voices, French and English.
LINES = [
    ('V-001', 'Maëlis', '[ton: bas] Le col est fermé depuis trois jours. Personne ne monte plus.', ''),
    ('V-002', 'Brannoc', 'Alors on passera par la rivière. Elle est gelée, ça porte.', ''),
    ('V-003', 'Vasric', 'Personne ne passe sans mon accord, et je ne l\'ai donné à personne.', ''),
    ('V-004', 'Ilyenne', '[pause: 400ms] La glace porte ceux que la rivière veut bien porter.', ''),
    ('V-005', 'Maëlis', 'Tu crois que la glace tiendra sous les chevaux ?', ''),
    ('V-006', 'Brannoc', 'Elle a tenu l\'hiver dernier. Elle tiendra encore un soir.', ''),
    ('V-007', 'Vasric', 'Vous parlez beaucoup pour des gens qui n\'ont pas de laissez-passer.', ''),
    ('V-008', 'Ilyenne', 'Écoutez. Le vent a tourné cette nuit, et il sent la cendre.', ''),
    ('V-009', 'Maëlis', 'Alors écris-le. Maintenant, pendant que je te regarde.', ''),
    ('V-010', 'Brannoc', '[soupir] On dort ici. On repart à l\'aube.', ''),
    ('V-011', 'Vasric', 'À l\'aube, la herse sera levée. Pas avant.', ''),
    ('V-012', 'Ilyenne', 'Je garderai la chandelle allumée, pour ceux qui reviennent.', ''),
    ('V-013', 'Maëlis', 'The pass has been closed for three days. Nobody goes up any more.', 'English'),
    ('V-014', 'Maëlis', 'Then write it down. Now, while I am watching you.', 'English'),
    ('V-015', 'Brannoc', 'Then we cross by the river. It is frozen, it will hold.', 'English'),
    ('V-016', 'Vasric', 'At dawn the gate will rise. Not before.', 'English'),
]
MODES = [
    ('M-001', 'Orla', 'Montez, la barque est sèche. Je vous passe avant la nuit.', ''),
    ('M-002', 'Orla', 'Tenez-vous au bord, et ne regardez pas l\'eau.', ''),
    ('M-003', 'Tom', 'The road is closed until morning, sir.', 'English'),
    ('M-004', 'Tom', 'I was told to wait for an answer.', 'English'),
]
HEARD = ['V-001', 'V-004', 'V-008', 'V-013', 'V-015', 'V-016', 'M-001', 'M-003']


def run(runtime, actor, session, operation, parameters, timeout=3600):
    job = runtime.submit(actor, session, operation, parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=timeout)
    if finished['state'] != 'Completed':
        raise SystemExit('%s failed: %s' % (operation, json.dumps(finished.get('error'),
                                                                  ensure_ascii=False)))
    return finished['outputs']


def point_library_at(folder):
    """Every store of the Tool at `folder`: this is how one process plays two machines."""
    library.personas = library.Collection(folder / 'personas', normalize_persona,
                                          FORMAT_PERSONA, 'persona')
    library.worlds = library.Collection(folder / 'worlds', normalize_world,
                                        'cytools-personarp-world', 'world')
    library.VOICES = stable.VOICES = folder / 'voices'
    sessions.SESSIONS = folder / 'sessions'
    batches.BATCHES = folder / 'batches'


def table(lines):
    rows = ['id;personnage;texte;langue'] + [';'.join(line) for line in lines]
    return '\n'.join(rows) + '\n'


def loudness(path):
    """Duration in seconds and RMS of a 16-bit mono WAV, without numpy."""
    with wave.open(str(path), 'rb') as handle:
        frames = handle.readframes(handle.getnframes())
        rate = handle.getframerate()
    samples = array('h', frames)
    if not samples:
        return 0.0, 0.0
    rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5 / 32768.0
    return len(samples) / rate, rms


def takes(outputs):
    """Every line of a task, checked from its folder."""
    folder = Path(outputs['folder'])
    lines = json.loads((folder / 'resultats.json').read_text(encoding='utf-8'))['lines']
    checked = []
    for line in lines:
        entry = {'id': line['id'], 'status': line['status'], 'mode': line.get('mode'),
                 'voice': line.get('voiceUsed'), 'language': line.get('languageUsed'),
                 'source': line.get('speakerSource'), 'file': line.get('file'),
                 'error': line.get('error', '')}
        if line['status'] == 'ok':
            seconds, rms = loudness(folder / line['file'])
            named = Path(line['file']).stem == line['id']
            entry.update(seconds=round(seconds, 2), rms=round(rms, 4), named=named,
                         ok=seconds >= 0.8 and rms >= 0.005 and named)
        else:
            entry['ok'] = False
        checked.append(entry)
    return checked


def words(text):
    text = re.sub(r'\[[^\]]*\]', ' ', text)
    text = unicodedata.normalize('NFKD', text.casefold())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return [word for word in re.findall(r'[a-z]+', text) if len(word) > 2]


def overlap(expected, heard):
    wanted, got = words(expected), set(words(heard))
    return sum(1 for word in wanted if word in got) / max(1, len(wanted))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true',
                        help='stop after the check: no voice generated, no GPU')
    arguments = parser.parse_args()

    base = Path(tempfile.mkdtemp(prefix='personarp-tasks-'))
    prepare, execute = base / 'machine-qui-prepare', base / 'machine-qui-execute'
    point_library_at(prepare)
    evidence = DATA / 'reports' / 'audio' / 'lots'
    evidence.mkdir(parents=True, exist_ok=True)

    from tool import create_runtime
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'folders': str(base), 'steps': []}
    failures = []

    def step(name, started, **details):
        entry = {'step': name, 'seconds': round(time.monotonic() - started, 1), **details}
        report['steps'].append(entry)
        print('%-44s %6.1f s' % (name, entry['seconds']), flush=True)
        return entry

    with create_runtime(base / 'jobs') as runtime:
        actor = runtime.authenticate(
            runtime.create_client('acceptance-batch', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']

        # ------------------------------------------------ the machine that prepares
        started = time.monotonic()
        listed = {item['id']: item for item in
                  run(runtime, actor, session, 'list_examples', {})['examples']}
        imported = run(runtime, actor, session, 'import_personas',
                       {'file': listed['01-valdrenn']['file']})
        maelis = next(identifier for identifier in imported['personas'] if 'maelis' in identifier)
        orla = library.personas.create({'name': 'Orla la Passeuse', 'voice': {
            'description': 'Une vieille femme à la voix rauque et chaleureuse, qui parle lentement.',
            'language': 'French'}})
        tom = library.personas.create({'name': 'Tom le Messager', 'voice': {
            'speaker': 'Ryan', 'language': 'English'}})
        step('import Valdrenn + two characters', started, personas=imported['personas'])

        english_voice = ''
        if not arguments.check_only:
            started = time.monotonic()
            take = run(runtime, actor, session, 'capture_voice_take', {
                'persona_id': maelis, 'description': ENGLISH_VOICE, 'model': '1.7B-VoiceDesign',
                'language': 'English', 'device': 'cuda', 'seed': 42, 'transcribe': True})
            voice = run(runtime, actor, session, 'create_stable_voice', {
                'name': 'Maëlis EN', 'audio': take['file'], 'transcript': take['transcript'],
                'persona_id': maelis, 'attach': True, 'language': 'English',
                'for_language': 'English', 'source': 'designed', 'description': ENGLISH_VOICE})
            english_voice = voice['id']
            shutil.copyfile(take['file'], evidence / 'maelis-voix-anglaise-reference.wav')
            step('real English voice for Maëlis', started, voice=english_voice,
                 take=round(take['durationSeconds'], 1), transcript=take['transcript'])

        started = time.monotonic()
        exported = run(runtime, actor, session, 'export_personas', {
            'persona_ids': imported['personas'] + [orla['id'], tom['id']], 'include_audio': True})
        bundle = base / 'personnages-valdrenn.zip'
        shutil.copyfile(exported['file'], bundle)
        step('export with the recordings', started, voices=exported['voices'],
             audio=exported['bundledAudio'])
        if english_voice and english_voice not in exported['voices']:
            failures.append('the English voice was not exported')

        # --------------------------------------------------- the machine that runs
        point_library_at(execute)
        common = {'personas': [str(bundle)], 'use_library': False}

        started = time.monotonic()
        checked = run(runtime, actor, session, 'speak_batch_file', {
            **common, 'text': table(LINES + MODES), 'dry_run': True})
        preview = {line['id']: line for line in checked['preview']}
        entry = step('check (dry run)', started, lines=checked['lines'], ready=checked['ready'],
                     failed=checked['failed'], groups=checked['groups'],
                     problems=checked['problems'], maelisEnglish=preview['V-013']['voiceUsed'])
        if checked['failed'] or checked['problems']:
            failures.append('check: %s' % entry)
        if english_voice and preview['V-013']['voiceUsed'] != english_voice:
            failures.append('Maëlis in English is not on her English voice: %s' % preview['V-013'])
        if arguments.check_only:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            return 1 if failures else 0

        started = time.monotonic()
        run(runtime, actor, session, 'speak_batch_file', {
            **common, 'text': table(LINES[:1]), 'name': 'chauffe'})
        step('warm-up (model load)', started)

        timings = {}
        for label, size in (('sequential', 1), ('automatic', 0)):
            started = time.monotonic()
            outputs = run(runtime, actor, session, 'speak_batch_file', {
                **common, 'text': table(LINES), 'name': label, 'batch_size': size})
            lines = takes(outputs)
            group = outputs['groups'][0] if outputs['groups'] else {}
            entry = step('%s (%d lines)' % (label, len(LINES)), started, done=outputs['done'],
                         failed=outputs['failed'], batch=outputs['batch'],
                         folder=outputs['folder'], group=group, lines=lines)
            timings[label] = entry['seconds']
            report[label] = entry
            bad = [line for line in lines if not line['ok']]
            if bad or outputs['failed']:
                failures.append('%s: %d bad take(s): %s' % (label, len(bad), bad[:3]))
            if any(line['source'] != 'task' for line in lines):
                failures.append('%s: a line was not spoken by the task\'s characters' % label)
        report['speedUp'] = round(timings['sequential'] / max(0.001, timings['automatic']), 2)

        started = time.monotonic()
        outputs = run(runtime, actor, session, 'speak_batch_file', {
            **common, 'text': table(MODES), 'name': 'modes'})
        lines = takes(outputs)
        report['modes'] = step('invented voice + preset speaker', started,
                               folder=outputs['folder'], groups=outputs['groups'], lines=lines)
        if sorted({line['mode'] for line in lines}) != ['custom', 'design'] \
                or not all(line['ok'] for line in lines):
            failures.append('modes: %s' % lines)

        started = time.monotonic()
        resumed = run(runtime, actor, session, 'speak_batch',
                      {'resume': report['automatic']['batch']})
        step('resume the batched task', started, skipped=resumed['skipped'],
             generated=len(resumed['groups']))
        if resumed['skipped'] != len(LINES) or resumed['groups']:
            failures.append('resume generated again: %s' % resumed)

        # Whisper: each take must say its own line.
        started = time.monotonic()
        texts = {identifier: text for identifier, _, text, _ in LINES + MODES}
        folders = {**{line[0]: Path(report['automatic']['folder']) for line in LINES},
                   **{line[0]: Path(report['modes']['folder']) for line in MODES}}
        heard = []
        for identifier in HEARD:
            audio = folders[identifier] / 'voix' / (identifier + '.wav')
            transcript = run(runtime, actor, session, 'transcribe', {'audio': str(audio)})['text']
            score = overlap(texts[identifier], transcript)
            heard.append({'id': identifier, 'expected': texts[identifier], 'heard': transcript,
                          'overlap': round(score, 2)})
            shutil.copyfile(audio, evidence / (identifier + '.wav'))
            if score < 0.6:
                failures.append('%s does not say its line: %r' % (identifier, transcript))
        report['heard'] = step('Whisper on %d takes' % len(heard), started, takes=heard)

        # The machine that ran the tasks kept nothing in its library.
        report['libraryUntouched'] = library.personas.list() == [] and not any(
            (execute / 'voices').glob('*.json'))
        if not report['libraryUntouched']:
            failures.append('the library of the machine that ran the tasks was written')
        folder = Path(report['automatic']['folder'])
        report['taskFolder'] = sorted(path.relative_to(folder).as_posix()
                                      for path in folder.rglob('*') if path.is_file())

    report['failures'] = failures
    report['passed'] = not failures
    target = DATA / 'reports' / 'batch-acceptance.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in (
        'speedUp', 'libraryUntouched', 'failures', 'passed')}, ensure_ascii=False, indent=2))
    for label in ('sequential', 'automatic'):
        group = report[label]['group']
        print('%-10s %6.1f s  batches=%s retries=%s per passage %.2f GB  peak %.1f GB / cap %.1f GB'
              % (label, report[label]['seconds'], group.get('batchSizes'),
                 group.get('memoryRetries'), (group.get('perPassageBytes') or 0) / 1024 ** 3,
                 (group.get('vramPeakBytes') or 0) / 1024 ** 3,
                 (group.get('limitBytes') or 0) / 1024 ** 3))
    for item in report['heard']['takes']:
        print('%-6s %.2f  %s' % (item['id'], item['overlap'], item['heard'][:90]))
    print('Report:', target)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
