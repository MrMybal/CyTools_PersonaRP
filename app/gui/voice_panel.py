"""The Voice tab: the engine, the speech models, and the stable voices.

Creating a stable voice is the flow this panel exists for, and it is deliberately three
explicit steps: capture a take of roughly a dozen seconds, listen to it, then keep it. The
take is written next to the library so it survives the job that produced it, and nothing is
registered as a voice until you ask.
"""
import webbrowser

from cytools_core import CyToolError
from ui_common import imgui, raw, tr

from personarp.paths import DATA
from personarp.schemas import LANGUAGES
from personarp.voice import delivery

from . import recorder, widgets
from .state import open_path


def sf_seconds(path):
    import soundfile
    info = soundfile.info(str(path))
    return info.frames / info.samplerate

SPEAKERS = ['Ryan', 'Aiden', 'Vivian', 'Serena', 'Uncle_Fu', 'Dylan', 'Eric', 'Ono_Anna', 'Sohee']
# Inside a sentence a language keeps its sentence form: "Dire en anglais", not "en Anglais".
IN_LANGUAGE = {language: 'in ' + language for language in LANGUAGES}
SOURCES = ['designed', 'generated', 'imported']


PHRASES = [
    "Bonjour. Voici ma voix, telle qu'elle sonnera dans les scènes.",
    "[ton: bas et lent] Approchez. [pause: 600ms] Je ne le répéterai pas.",
    "[emotion: amusement] Vous êtes sérieux ? Vraiment ?",
    "Un souvenir cédé est un morceau de votre propre existence.",
]
# Examples in the language being tried: a French sentence read "in English" proves nothing.
PHRASES_BY_LANGUAGE = {
    'English': [
        "Hello. This is my voice, the way it will sound in the scenes.",
        "[tone: low and slow] Come closer. [pause: 600ms] I will not say it twice.",
        "[emotion: amusement] Are you serious? Really?",
        "A memory you give away is a piece of your own life.",
    ],
}


def language_combo(label, current, empty):
    """A language, or '' for the character's own."""
    choices = [''] + LANGUAGES
    captions = [tr(empty)] + [tr(language) for language in LANGUAGES]
    index = choices.index(current) if current in choices else 0
    changed, index = imgui.combo(label, index, captions)
    return choices[index], changed


def own_language(app, persona):
    """The character's language, read the way the runtime reads it."""
    voice = (persona or {}).get('voice') or {}
    main = next((v for v in app.voices if v['id'] == voice.get('voice_id')), None)
    return delivery.native_language(persona or {}, main)


def language_summary(app, persona, language):
    """In one line, which voice will speak this language — from the same sheet the runtime reads."""
    voice = (persona or {}).get('voice') or {}
    known = {entry['id']: entry for entry in app.voices}
    main = known.get(voice.get('voice_id', ''))
    entry = delivery.language_entry(persona or {}, language)
    if entry is None or entry['source'] == 'same':
        if main:
            who = tr('its stable voice "%s"') % main['name']
        elif (voice.get('description') or '').strip():
            who = tr('its invented voice')
        else:
            who = tr('the preset speaker %s') % (voice.get('speaker') or 'Ryan')
        accent = (entry or {}).get('accent', 'keep')
        text = tr('%s: the same voice — %s, %s') % (
            tr(language), who, tr('accent kept') if accent == 'keep' else tr('native pronunciation'))
        if entry is None:
            text += tr(' (nothing configured for this language)')
        return text
    if entry['source'] == 'voice':
        other = known.get(entry['voice_id'])
        if other is None:
            return tr('%s: the chosen voice is missing — the main voice will be used') % tr(language)
        return tr('%s: its own stable voice "%s"') % (tr(language), other['name'])
    if entry['source'] == 'design':
        return tr('%s: an invented voice — %s') % (tr(language), entry['description'][:80])
    return tr('%s: the preset speaker %s') % (tr(language), entry['speaker'])


def _bench(app):
    """Try any voice on any text, with nothing else open."""
    imgui.separator_text(tr('Try a voice'))
    state = getattr(app, 'bench', None)
    if state is None:
        state = app.bench = {'voice_id': '', 'speaker': '', 'text': PHRASES[0],
                             'device': 'cuda', 'language': ''}

    voices = [{'id': v['id'], 'name': '%s — %s%s' % (
        v['name'], v.get('persona_id') or 'libre',
        ' — ' + tr(v['language']) if v.get('language') not in (None, '', 'Auto') else '')}
        for v in app.voices]
    chosen, picked = widgets.picker(tr('Voice'), state['voice_id'], voices,
                                    '(the voice of the selected character)')
    if picked:
        state['voice_id'] = chosen
        state['speaker'] = ''
    if not state['voice_id']:
        widgets.combo(state, 'speaker', tr('or a preset speaker'), [''] + SPEAKERS,
                      [tr('(no, use the character)')] + SPEAKERS)
    state['language'], _ = language_combo(tr('Language spoken'), state.get('language', ''),
                                          "(the character's own language)")
    if state['language'] and not state['voice_id'] and not state['speaker'] and app.persona:
        # Said before it runs, so the choice made on the sheet is visible where it is heard.
        raw().text_disabled(language_summary(app, app.persona, state['language']))

    imgui.text(tr('Text to say'))
    _, state['text'] = imgui.input_text_multiline('##bench-text', state['text'], (-1, 54))
    for index, phrase in enumerate(PHRASES_BY_LANGUAGE.get(state['language'], PHRASES)):
        if index:
            imgui.same_line()
        if widgets.small_button(tr('Example %d') % (index + 1)):
            state['text'] = phrase
    widgets.combo(state, 'device', tr('Device'), ['cuda', 'cpu'], [tr('NVIDIA GPU'), tr('CPU')])

    ready = bool(state['text'].strip()) and (state['voice_id'] or state['speaker']
                                             or app.persona_id)
    imgui.begin_disabled(app.busy or not ready)
    if widgets.button('Say it'):
        payload = {'text': state['text'], 'device': state['device'],
                   'language': state.get('language', '')}
        if state['voice_id']:
            payload['voice_id'] = state['voice_id']
        elif state['speaker']:
            payload['voice'] = {'speaker': state['speaker'], 'voice_id': '', 'description': ''}
        else:
            payload['persona_id'] = app.persona_id
        app.submit('speak', payload, 'speak')
    imgui.end_disabled()
    if app.busy and app.purpose == 'speak':
        imgui.same_line()
        raw().text_disabled(tr('Speaking...'))
    raw().text_disabled(tr('Delivery marks work here: [ton: sourd], [pause: 400ms], '
                           '[emotion: soulagement]. The player is at the bottom of the window.'))


def _engine(app):
    engine = (app.voice_engine or {})
    report = engine.get('report') or {}
    installed = bool(engine.get('installed'))
    imgui.separator_text(tr('Speech engine'))
    raw().text_wrapped(
        (tr('Installed') + ' — torch %s, %s' % (report.get('torch', '?'),
                                                report.get('device', 'cpu')))
        if installed else
        tr('Not installed. The engine is private to this Tool and takes about 8 GB. Nothing '
           'can be spoken until it is built.'))
    imgui.begin_disabled(app.busy)
    if widgets.button('Install / repair the speech engine'):
        app.submit('install_voice_engine', {'cpu_only': getattr(app, 'engine_cpu_only', False)},
                   'install_voice_engine')
    imgui.same_line()
    _, app.engine_cpu_only = imgui.checkbox(tr('CPU only (much slower)'),
                                            getattr(app, 'engine_cpu_only', False))
    imgui.same_line()
    if widgets.button('Release the speech processes'):
        app.submit('release_voice', {}, 'release_voice')
    imgui.end_disabled()
    workers = engine.get('workers') or {}
    if workers:
        raw().text_disabled(tr('Workers: ') + ', '.join(
            '%s=%s' % (name, info.get('state', '?')) for name, info in workers.items()))


def _models(app):
    imgui.separator_text(tr('Speech models'))
    accepted = getattr(app, 'voice_license', None)
    if accepted is None:
        accepted = app.voice_license = {}
    imgui.begin_disabled(app.busy)
    if widgets.button('Refresh##voice-models'):
        app.submit('list_voice_models', {'verify': False}, 'list_voice_models')
    imgui.same_line()
    if widgets.button('Verify the installed weights##voice'):
        app.submit('list_voice_models', {'verify': True}, 'list_voice_models')
    imgui.end_disabled()
    imgui.begin_child('voice-models', (0, 190), imgui.ChildFlags_.borders)
    for item in app.voice_models:
        imgui.push_id('vm-' + item['id'])
        state = tr('installed') if item['installed'] else (
            tr('partly downloaded') if item.get('presentBytes') else tr('not installed'))
        imgui.text('%s — %s' % (item['name'], state))
        raw().text_disabled('%.2f GB · %s · %s' % (item['sizeBytes'] / 1e9, item['id'],
                                                   item.get('verification', '')))
        if item.get('notes'):
            raw().text_wrapped(item['notes'])
        raw().text_disabled(tr('Licence: ') + (item.get('license') or tr('not declared')))
        if item.get('source') and widgets.small_button('Official page and licence'):
            webbrowser.open(item['source'])
        checked = accepted.get(item['id'], item.get('licenseAccepted', False))
        _, checked = imgui.checkbox(tr('I personally accept this licence'), checked)
        accepted[item['id']] = checked
        imgui.begin_disabled(app.busy or not checked)
        if widgets.button('Download / resume' if not item['installed'] else 'Repair / verify'):
            app.submit('install_voice_model', {'model': item['id'], 'accept_license': True},
                       'install_voice_model')
        imgui.end_disabled()
        imgui.separator()
        imgui.pop_id()
    imgui.end_child()
    raw().text_wrapped(tr('Cloning needs a Base variant; a preset speaker needs CustomVoice; an '
                          'invented voice needs VoiceDesign. The Tool picks the right one for '
                          'what you ask and says so when it substitutes.'))


def _library(app):
    imgui.separator_text(tr('Stable voices'))
    if not app.voices:
        raw().text_disabled(tr('No stable voice yet. Capture a take below to create one.'))
    for item in app.voices:
        imgui.push_id('voice-' + item['id'])
        raw().text('%s — %.0f s — %s — %s' % (item['name'], item['seconds'],
                                              tr(item['source']),
                                              tr(item.get('language') or 'Auto')))
        raw().text_disabled('%s · %s%s' % (item['id'], item.get('model', ''),
                                           '' if item.get('available')
                                           else tr('  · recording missing')))
        if widgets.small_button('Listen to the take'):
            app.play_file(item.get('reference_audio', ''))
        imgui.same_line()
        imgui.begin_disabled(app.busy)
        if widgets.small_button('Test on a sentence'):
            bench = getattr(app, 'bench', None) or {}
            app.submit('speak', {'voice_id': item['id'],
                                 'text': bench.get('text') or PHRASES[0],
                                 'language': bench.get('language', ''),
                                 'device': bench.get('device', 'cuda')}, 'speak')
        imgui.end_disabled()
        imgui.same_line()
        if widgets.small_button('Check'):
            try:
                result = app.call('verify_voice', {'voice_id': item['id']})
                app.notice = (tr('Voice "%s" is intact.') % item['name']) if result['ok'] \
                    else result['reason']
            except CyToolError as exc:
                app.error = str(exc)
        imgui.same_line()
        if widgets.small_button('Attach to the selected character') and app.persona:
            app.persona['voice'] = {**app.persona['voice'], 'voice_id': item['id'],
                                    'enabled': True}
            app.save_persona()
        imgui.same_line()
        if widgets.small_button('Move to trash'):
            try:
                app.call('remove_voice', {'voice_id': item['id']})
                app.notice = 'Voice moved to data/voices/.trash — nothing was deleted.'
                app.refresh_voices()
            except CyToolError as exc:
                app.error = str(exc)
        imgui.separator()
        imgui.pop_id()


def _capture(app):
    imgui.separator_text(tr('Create a stable voice'))
    raw().text_wrapped(tr(
        'Step 1 — produce about 12 to 24 seconds of speech. Describe the voice you want and it '
        'is invented, or pick a preset speaker. Step 2 — listen. Step 3 — keep it: every later '
        'line of the character is cloned from that recording.'))
    state = getattr(app, 'capture', None)
    if state is None:
        state = app.capture = {'description': '', 'speaker': 'Vivian', 'text': '',
                               'use_speaker': False, 'name': '', 'device': 'cuda'}
    widgets.checkbox(state, 'use_speaker', tr('Use a preset speaker instead of a description'))
    if state['use_speaker']:
        widgets.combo(state, 'speaker', tr('Preset speaker'), SPEAKERS)
    else:
        widgets.multiline(state, 'description', tr('Voice to invent'), 54)
        raw().text_disabled(tr('For example: femme, fin de vingtaine, grave et posee, debit lent, '
                               'chaleur contenue.'))
    state['language'], _ = language_combo(tr('Language of the take'), state.get('language', ''),
                                          "(the character's own language)")
    if state['language'] and app.persona \
            and state['language'] != own_language(app, app.persona):
        raw().text_disabled(tr('A take read in this language gives a voice that really belongs '
                               'to it. Describe it as a native speaker, write the text in that '
                               'language — or leave it empty for a standard passage.'))
    widgets.multiline(state, 'text', tr('What the take says (empty uses a standard passage)'), 54)
    widgets.combo(state, 'device', tr('Device'), ['cuda', 'cpu'], ['NVIDIA GPU', 'CPU'])

    imgui.begin_disabled(app.busy or not app.persona)
    if widgets.button('Capture a take'):
        payload = {'persona_id': app.persona_id, 'text': state['text'],
                   'device': state['device'], 'transcribe': True,
                   'language': state.get('language', '')}
        if state['use_speaker']:
            payload['speaker'] = state['speaker']
        else:
            payload['description'] = state['description']
            payload['model'] = '1.7B-VoiceDesign'
        app.submit('capture_voice_take', payload, 'capture_voice_take')
    imgui.end_disabled()
    if not app.persona:
        imgui.same_line()
        raw().text_disabled(tr('Select a character first.'))

    take = getattr(app, 'take', None)
    if not take:
        return
    imgui.separator()
    imgui.text(tr('Take: %.1f s') % take.get('durationSeconds', 0.0))
    imgui.same_line()
    raw().text_disabled(tr('in the ideal range') if take.get('inRange')
                        else take.get('advice', ''))
    if widgets.button('Listen to the take'):
        app.play_file(take['file'])
    imgui.same_line()
    if widgets.button('Open the take folder'):
        open_path(DATA / 'voices' / 'takes')
    imgui.text(tr('Exact words heard in the take (used to clone it)'))
    _, take['transcript'] = imgui.input_text_multiline('##take-transcript',
                                                       take.get('transcript', ''), (-1, 54))
    _, state['name'] = imgui.input_text(tr('Name of the voice'),
                                        state.get('name') or ((app.persona or {}).get('name', '')))
    language = take.get('language') or ''
    attach_as = _attach_as(app, state, language)
    imgui.begin_disabled(app.busy or not state['name'].strip())
    if widgets.button('Keep this take as a stable voice'):
        app.submit('create_stable_voice', {
            'name': state['name'], 'audio': take['file'], 'transcript': take['transcript'],
            'persona_id': app.persona_id, 'attach': True, 'for_language': attach_as,
            'language': language or own_language(app, app.persona),
            'source': 'generated' if state['use_speaker'] else 'designed',
            'description': state['description']}, 'create_stable_voice')
    imgui.end_disabled()
    imgui.same_line()
    if widgets.button('Discard this take'):
        app.take = None


def _attach_as(app, state, language):
    """Main voice, or the voice of one language only. Returns '' or that language."""
    if not app.persona:
        return ''
    if not language or language == own_language(app, app.persona):
        raw().text_disabled(tr('It becomes the main voice of %s.') % app.persona.get('name', ''))
        return ''
    choices = ['language', 'main']
    captions = [tr('Its voice %s only — the main voice is kept') % tr(IN_LANGUAGE[language]),
                tr('Its main voice, replacing the current one')]
    current = state.get('attach_as', 'language')
    index = choices.index(current) if current in choices else 0
    _, index = imgui.combo(tr('Keep it as'), index, captions)
    state['attach_as'] = choices[index]
    return language if choices[index] == 'language' else ''


def _import(app):
    imgui.separator_text(tr('Use your own recording'))
    raw().text_wrapped(tr('A WAV of roughly 12 to 24 seconds of one clear voice. It is '
                          'transcribed so the clone knows what is being said.'))
    state = getattr(app, 'import_voice', None)
    if state is None:
        state = app.import_voice = {'audio': '', 'name': '', 'transcript': '', 'language': ''}
    widgets.text_field(state, 'audio', tr('Recording (full path, or a file in data/inputs)'))
    imgui.same_line()
    if widgets.button('Open data/inputs##voice'):
        open_path(DATA / 'inputs')
    # Or record it here: 12 to 24 seconds of one clear voice, the recording stops at 30 s.
    recorder.microphone_picker(app)
    recorded = recorder.controls(app, 'voice', 30.0, tr('Record from the microphone'))
    if recorded:
        state['audio'] = recorded
        seconds = sf_seconds(recorded)
        app.notice = tr('Recorded %.1f s: %s') % (seconds, recorded)
        if not 12.0 <= seconds <= 24.0:
            app.notice += ' ' + tr('Between 12 and 24 seconds gives the steadiest clone.')
    widgets.text_field(state, 'name', tr('Name of the voice'))
    widgets.multiline(state, 'transcript',
                      tr('Exact words (leave empty to transcribe automatically)'), 44)
    state['language'], _ = language_combo(tr('Language of the recording'),
                                          state.get('language', ''),
                                          "(the character's own language)")
    attach_as = _attach_as(app, state, state['language'])
    imgui.begin_disabled(app.busy or not (state['audio'].strip() and state['name'].strip()))
    if widgets.button('Create a stable voice from this recording'):
        app.submit('create_stable_voice', {
            'name': state['name'], 'audio': state['audio'], 'transcript': state['transcript'],
            'persona_id': app.persona_id, 'attach': bool(app.persona_id), 'source': 'imported',
            'for_language': attach_as,
            'language': state['language'] or own_language(app, app.persona),
            'transcribe': not state['transcript'].strip()}, 'create_stable_voice')
    imgui.end_disabled()


def voice_tab(app):
    # Models are not shipped: on a fresh install, say first what has to be downloaded.
    engine = app.voice_engine or {}
    warning = imgui.ImVec4(1.0, 0.75, 0.35, 1.0)
    if engine and not engine.get('installed'):
        imgui.text_colored(warning, tr('The speech engine is not installed yet: install it below '
                                       '(Speech engine), then the speech models you need. Nothing '
                                       'can be spoken before.'))
    elif app.voice_models and not any(item.get('installed') for item in app.voice_models
                                      if item.get('backend', 'qwen3tts') == 'qwen3tts'):
        imgui.text_colored(warning, tr('No speech model is installed yet: download at least the '
                                       '1.7B Base model below (Speech models) to hear a stable '
                                       'voice.'))
    imgui.begin_child('voice-body', (0, 470), imgui.ChildFlags_.borders)
    _bench(app)
    _library(app)
    _capture(app)
    _import(app)
    _engine(app)
    _models(app)
    imgui.end_child()
