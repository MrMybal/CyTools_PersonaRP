"""Real acceptance of translation and per-language voices: a model and the speech engine run.

On a throwaway character that borrows an existing stable voice, it:

  1. translates a French scene into English with a language model chosen for the job;
  2. speaks the English line with the same voice, accent kept (nothing configured);
  3. speaks it with the same voice, native pronunciation (timbre only);
  4. captures an English take from a written description, keeps it as the English voice
     only, and speaks the line with it — the French voice must stay the main voice;
  5. photographs the Scene tab and the sheet's voice section with that character open.

Every take is transcribed back by Whisper and compared with the English text, which says
whether the words are intelligible. Whether two takes sound like the same person is not
measured here: listen to data/reports/audio/multilingue/.

The throwaway character, its scene and the English voice are moved to .trash at the end;
nothing is deleted. About two to three minutes of GPU time.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_translation.py [translation-model]
Writes data/reports/translation-acceptance.json.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from personarp import sessions                                      # noqa: E402
from personarp.paths import DATA                                    # noqa: E402
from personarp.voice import stable                                  # noqa: E402
from tool import create_runtime                                     # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else 'qwen3-8b'
BORROWED = 'alcyone-premiere-archiviste'
EVIDENCE = DATA / 'reports' / 'audio' / 'multilingue'
SCENE = [
    ('user', 'Je voudrais racheter mon souvenir. Combien ?'),
    ('assistant', "[ton: sec] Je vous entends. [pause: 400ms] Et la réponse reste non. "
                  "*Elle referme le registre sans vous regarder.* Le prix n'est pas "
                  "négociable, il est seulement exact."),
]
ENGLISH_VOICE = ('A woman in her forties from London, low and dry voice, slow and precise '
                 'delivery, faintly amused, native British English.')


def run(runtime, actor, session, operation, parameters, timeout=1800):
    job = runtime.submit(actor, session, operation, parameters)
    finished = runtime.wait(actor, job['jobId'], timeout=timeout)
    if finished['state'] != 'Completed':
        raise SystemExit('%s failed: %s' % (operation, json.dumps(finished.get('error'),
                                                                  ensure_ascii=False)))
    return finished['outputs']


def words(text):
    text = re.sub(r'\[[^\]]*\]|\*[^*]*\*', ' ', text or '')
    return re.findall(r"[a-z']+", text.lower())


def overlap(expected, heard):
    """Share of the expected words Whisper heard, order ignored."""
    wanted = words(expected)
    got = set(words(heard))
    return round(sum(1 for word in wanted if word in got) / max(1, len(wanted)), 2)


def screenshot(tab, name, persona_id, session_id, sheet=''):
    started = time.time()
    command = [str(ROOT / 'runtime/python/Scripts/python.exe'), str(APP / 'desktop.py'),
               '--smoke-tab', tab, '--strict-ui', '--smoke-persona', persona_id,
               '--smoke-session', session_id, '--smoke-name', name]
    if sheet:
        command += ['--smoke-sheet', sheet]
    finished = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=300)
    picture = DATA / 'reports' / ('ui-%s.png' % name)
    fresh = picture.is_file() and picture.stat().st_mtime >= started
    return {'tab': name, 'exitCode': finished.returncode, 'fresh': fresh, 'file': str(picture),
            'output': (finished.stderr or '')[-400:] if finished.returncode else ''}


def main():
    report = {'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'translationModel': MODEL, 'steps': []}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not stable.exists(BORROWED):
        raise SystemExit('The voice %s is not in the library.' % BORROWED)
    with create_runtime(DATA / 'jobs') as runtime:
        client = runtime.create_client('acceptance-translation', ['network', 'filesystemExternal'])
        actor = runtime.authenticate(client['token'])
        session = runtime.create_session(actor, temporary=False)['sessionId']

        def step(name, started, **values):
            entry = {'step': name, 'seconds': round(time.monotonic() - started, 1), **values}
            report['steps'].append(entry)
            print(json.dumps(entry, ensure_ascii=False)[:400])
            return entry

        created = run(runtime, actor, session, 'create_persona', {'persona': {
            'name': 'Essai multilingue (acceptance)',
            'voice': {'voice_id': BORROWED, 'language': 'French', 'enabled': True,
                      'annotations': True}}})
        persona_id = created['id']
        scene = run(runtime, actor, session, 'new_session',
                    {'persona_id': persona_id, 'title': 'Acceptance translation'})
        stored = sessions.get(persona_id, scene['id'])
        for role, content in SCENE:
            sessions.append_turn(stored, role, content)
        sessions.save(stored)
        english_voice, take_file = '', ''
        try:
            started = time.monotonic()
            translated = run(runtime, actor, session, 'translate', {
                'persona_id': persona_id, 'session_id': scene['id'], 'target_language': 'English',
                'llm_model': MODEL, 'device': 'cuda'})
            line = next(item for item in translated['translations'] if item['role'] == 'assistant')
            step('translate', started, model=translated['model'], device=translated['device'],
                 modelSeconds=translated['seconds'], marksLost=translated['marksLost'],
                 translations=[{'turn': item['turn'], 'text': item['text']}
                               for item in translated['translations']])
            english = line['text']
            report['marksKept'] = all(mark in english for mark in ('[ton: sec]', '[pause: 400ms]'))

            def speak(name, language):
                started = time.monotonic()
                take = run(runtime, actor, session, 'speak_turn', {
                    'persona_id': persona_id, 'session_id': scene['id'], 'turn': 1,
                    'language': language, 'device': 'cuda'})
                target = EVIDENCE / ('%s.wav' % name)
                shutil.copyfile(take['file'], target)
                heard = run(runtime, actor, session, 'transcribe',
                            {'audio': take['file'], 'device': 'cuda', 'timestamps': False})
                expected = english if language else SCENE[1][1]
                return step('speak_turn ' + name, started, language=language or 'French',
                            durationSeconds=round(take['durationSeconds'], 2),
                            voicePlan=take['voicePlan'], note=take.get('note', ''),
                            heard=heard['text'],
                            wordsHeard=overlap(expected, heard['text']) if language else None,
                            file=str(target), keptWithScene=take['file'])

            speak('en-meme-voix-accent', 'English')

            persona = run(runtime, actor, session, 'get_persona', {'persona_id': persona_id})['persona']
            persona['voice']['languages'] = [{'language': 'English', 'source': 'same',
                                              'accent': 'native'}]
            run(runtime, actor, session, 'save_persona', {'persona': persona})
            speak('en-meme-timbre-prononciation-native', 'English')

            started = time.monotonic()
            take = run(runtime, actor, session, 'capture_voice_take', {
                'persona_id': persona_id, 'description': ENGLISH_VOICE,
                'model': '1.7B-VoiceDesign', 'language': 'English', 'device': 'cuda', 'seed': 42,
                'transcribe': True})
            take_file = take['file']
            shutil.copyfile(take['file'], EVIDENCE / 'prise-anglaise.wav')
            step('capture_voice_take English', started, language=take['language'],
                 durationSeconds=round(take['durationSeconds'], 2), inRange=take['inRange'],
                 transcript=take['transcript'])
            started = time.monotonic()
            voice = run(runtime, actor, session, 'create_stable_voice', {
                'name': 'Essai EN (acceptance)', 'audio': take['file'],
                'transcript': take['transcript'], 'persona_id': persona_id, 'attach': True,
                'language': 'English', 'for_language': 'English', 'source': 'designed',
                'description': ENGLISH_VOICE})
            english_voice = voice['id']
            sheet = run(runtime, actor, session, 'get_persona', {'persona_id': persona_id})['persona']
            step('create_stable_voice for English only', started, id=english_voice,
                 forLanguage=voice['forLanguage'],
                 mainVoiceKept=sheet['voice']['voice_id'] == BORROWED,
                 englishEntry=sheet['voice']['languages'])
            report['mainVoiceKept'] = sheet['voice']['voice_id'] == BORROWED
            speak('en-voix-anglaise-propre', 'English')
            french = speak('fr-voix-principale', '')
            report['frenchStillMainVoice'] = french['voicePlan'].get('voice_id') == BORROWED

            run(runtime, actor, session, 'release_voice', {})
        except BaseException as exc:                        # noqa: BLE001 - cleaned up below
            report['error'] = repr(exc)

    # The window runs its own Runtime on the same data; this one is closed first so the
    # two never share the job store.
    if 'error' not in report:
        report['screenshots'] = [
            screenshot('Scene', 'multilingue-scene', persona_id, scene['id']),
            screenshot('Characters', 'multilingue-fiche-voix', persona_id, scene['id'],
                       sheet='Voice')]

    # Out of the way, never deleted.
    with create_runtime(DATA / 'jobs') as runtime:
        actor = runtime.authenticate(
            runtime.create_client('acceptance-cleanup', ['filesystemExternal'])['token'])
        session = runtime.create_session(actor, temporary=True)['sessionId']
        if english_voice:
            moved = run(runtime, actor, session, 'remove_voice', {'voice_id': english_voice})
            if take_file and Path(take_file).is_file():
                Path(take_file).replace(Path(moved['trash']) / Path(take_file).name)
        run(runtime, actor, session, 'remove_session',
            {'persona_id': persona_id, 'session_id': scene['id']})
        run(runtime, actor, session, 'remove_persona', {'persona_id': persona_id})
    # The scene's kept takes live beside its sessions; the whole folder goes too.
    folder = sessions.folder(persona_id)
    if folder.is_dir():
        trash = sessions.SESSIONS / '.trash'
        trash.mkdir(parents=True, exist_ok=True)
        folder.replace(trash / (folder.name + '-' + time.strftime('%Y%m%d-%H%M%S')))

    path = DATA / 'reports' / 'translation-acceptance.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(path)
    if 'error' in report:
        raise SystemExit('Failed: ' + report['error'])


if __name__ == '__main__':
    main()
