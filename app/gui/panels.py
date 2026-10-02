"""The tabs of the desktop window.

Each panel edits state and submits operations; none of them talks to a model directly.
"""
import json
import sys
import webbrowser
from pathlib import Path

from cytools_core import CyToolError
from ui_common import imgui, raw, tr

from personarp import scene as scene_module
from personarp import takes
from personarp import translation as translation_module
from personarp.paths import DATA, EXPORTS, read_json
from personarp.schemas import (LANGUAGES, normalize_language_voice, normalize_persona,
                               normalize_world)

from . import recorder, widgets
from .comfyui_panel import comfyui_tab
from .discussion_panel import discussion
from .gallery import library_gallery, viewer as picture_viewer
from .images_panel import references as reference_photographs
from .state import open_path
from .voice_panel import IN_LANGUAGE, language_summary, own_language

# Lets an acceptance run open one section of the sheet and photograph it.
SHEET_TAB = sys.argv[sys.argv.index('--smoke-sheet') + 1] if '--smoke-sheet' in sys.argv else ''
# ... and scroll it to the end, where the last section added to it lives.
SHEET_BOTTOM = '--smoke-scroll-bottom' in sys.argv

SCENE_ROWS = [('beat', 'Beat'), ('action', 'Action'), ('appearance', 'Appearance'),
              ('pose', 'Pose'), ('expression', 'Expression'), ('mood', 'Mood')]


# --------------------------------------------------------------------- conversation

def _draw_scene(directive, prompts, identity):
    """The directive, visible and copyable in the conversation, never spoken."""
    if not directive:
        return
    imgui.push_id('scene-' + identity)
    summary = scene_module.scene_summary(directive)
    if imgui.collapsing_header(tr('Scene description') + (' — ' + summary if summary else '')):
        raw().text_disabled(tr('Data for an image or video tool. It is never read aloud.'))
        for key, caption in SCENE_ROWS:
            value = str(directive.get(key) or '')
            if value:
                imgui.text(tr(caption) + ':')
                imgui.same_line()
                raw().text_wrapped(value)
        beats = directive.get('motion') or []
        if beats:
            imgui.text(tr('Movement') + ':')
            for beat in beats:
                raw().text_wrapped('  %.1fs — %s' % (float(beat.get('at', 0)),
                                                     beat.get('action', '')))
        camera, setting = directive.get('camera') or {}, directive.get('setting') or {}
        line = ', '.join(x for x in (camera.get('shot'), camera.get('angle'), camera.get('lens'),
                                     camera.get('movement')) if x)
        if line:
            imgui.text(tr('Camera') + ': ')
            imgui.same_line()
            raw().text_wrapped(line)
        line = ', '.join(x for x in (setting.get('location'), setting.get('time'),
                                     setting.get('weather'), setting.get('lighting')) if x)
        if line:
            imgui.text(tr('Setting') + ': ')
            imgui.same_line()
            raw().text_wrapped(line)
        for key, caption in (('image_prompt', 'Image prompt'), ('video_prompt', 'Video prompt'),
                             ('negative_prompt', 'Negative prompt')):
            value = str((prompts or {}).get(key) or directive.get(key) or '')
            if value:
                imgui.separator()
                imgui.text(tr(caption))
                imgui.input_text_multiline('##' + key + identity, value, (-1, 46),
                                           raw().InputTextFlags_.read_only)
        payload = json.dumps({**directive, **(prompts or {})}, ensure_ascii=False, indent=2)
        if widgets.button('Copy the JSON##' + identity):
            raw().set_clipboard_text(payload)
        imgui.same_line()
        raw().text_disabled(tr('Paste it into an image or video tool, or export the session.'))
    imgui.pop_id()


def conversation(app):
    persona = app.persona
    if persona is None:
        raw().text_disabled(tr('Create a character in the Characters tab to start a scene.'))
        return
    raw().text(tr('Playing: ') + persona.get('name', ''))
    imgui.same_line()
    raw().text_disabled('  ' + (persona['generation'].get('llm_model') or '?') + ' / '
                        + persona['generation'].get('device', 'cpu').upper()
                        + ('  ·  ' + tr('scene description on') if persona['media'].get('enabled')
                           else ''))

    imgui.begin_disabled(app.busy)
    entries = getattr(app, 'sessions', [])
    identifiers = [entry['id'] for entry in entries]
    captions = ['%s (%d)' % (entry.get('title') or entry['id'], entry.get('turns', 0))
                for entry in entries]
    if entries:
        index = identifiers.index(app.session_id) if app.session_id in identifiers else 0
        changed, index = imgui.combo('Scene', index, captions)
        if changed:
            app.session_id = identifiers[index]
            app.reload_conversation()
        imgui.same_line()
    if widgets.button('New scene'):
        try:
            app.session_id = ''
            app.ensure_session()
            app.notice = 'New scene started.'
        except CyToolError as exc:
            app.error = str(exc)
    imgui.end_disabled()

    options = _translation_bar(app, persona)
    language = options['language']
    shown = options['show']

    imgui.begin_child('transcript', (0, 330), imgui.ChildFlags_.borders)
    if not app.turns:
        raw().text_disabled(tr('The scene will appear here.'))
    for index, turn in enumerate(app.turns):
        imgui.push_id('turn-%d' % index)
        speaker = tr('You') if turn.get('role') == 'user' else persona.get('name', 'Character')
        imgui.separator_text(speaker)
        content = str(turn.get('content', ''))
        translated = ((turn.get('translations') or {}).get(language) or {})
        if shown != 'translation' or not translated.get('text'):
            if turn.get('role') == 'assistant':
                parsed = scene_module.split_reply(content)
                raw().text_wrapped(scene_module.strip_annotations(parsed['text']))
                marks = scene_module.parse_annotations(parsed['text'])
                if marks:
                    raw().text_disabled(tr('Delivery: ') + ', '.join(
                        '%s=%s' % (tr(MARK_CAPTIONS.get(m['kind'], m['kind'])), m['value'])
                        for m in marks))
            else:
                raw().text_wrapped(content)
        if shown != 'original' and translated.get('text'):
            imgui.text_colored(imgui.ImVec4(0.55, 0.80, 1.0, 1.0), tr(language))
            imgui.same_line()
            raw().text_wrapped(scene_module.strip_annotations(translated['text']))
            if translated.get('marksLost'):
                raw().text_disabled(tr('Marks lost in translation: ')
                                    + ' '.join(translated['marksLost']))
            if translated.get('termsMissed'):
                imgui.text_colored(imgui.ImVec4(1.0, 0.75, 0.35, 1.0),
                                   tr('Terms not kept: ') + '; '.join(translated['termsMissed']))
        if turn.get('role') == 'assistant':
            _turn_voice(app, index, turn, language, translated)
            _draw_scene(turn.get('scene') or scene_module.split_reply(content)['scene'],
                        turn.get('prompts'), str(index))
        imgui.pop_id()
    if app.busy and app.purpose == 'chat':
        imgui.separator_text(persona.get('name', 'Character'))
        raw().text_disabled(tr('Writing...'))
    imgui.end_child()

    imgui.text(tr('Your message — Enter sends, Ctrl+Enter adds a line'))
    entered, app.draft = imgui.input_text_multiline(
        '##composer', app.draft, (-1, 80),
        raw().InputTextFlags_.enter_returns_true | raw().InputTextFlags_.ctrl_enter_for_new_line)
    send = entered and not raw().get_io().key_ctrl
    imgui.begin_disabled(app.busy)
    if widgets.button('Send'):
        send = True
    imgui.same_line()
    if widgets.button('Preview the prompt'):
        try:
            outputs = app.call('preview_prompt', {'persona_id': app.persona_id,
                                                  'session_id': app.session_id,
                                                  'text': app.draft})
            app.prompt_preview = json.dumps(outputs['messages'], ensure_ascii=False, indent=2)
            app.notice = tr('Prompt assembled: %d characters, dropped sections: %s') % (
                outputs['context']['promptCharacters'],
                ', '.join(outputs['context']['droppedSections']) or tr('none'))
        except CyToolError as exc:
            app.error = str(exc)
    imgui.same_line()
    if widgets.button('Open the scene folder'):
        open_path(DATA / 'sessions' / app.persona_id)
    imgui.end_disabled()
    # Dictation: the microphone is recorded here, then transcribed by Whisper like any file;
    # the words are added to the message, which is sent only when you send it.
    imgui.same_line()
    imgui.begin_disabled(app.busy)
    dictated = recorder.controls(app, 'dictation', 120.0, tr('Dictate'))
    imgui.end_disabled()
    if dictated:
        app.submit('transcribe', {
            'audio': dictated, 'timestamps': False,
            'device': 'cpu' if (app.voice_engine or {}).get('cpuOnly') else 'cuda'}, 'dictation')

    if send and app.draft.strip() and not app.busy:
        try:
            session_id = app.ensure_session()
            text = app.draft
            app.draft = ''
            app.submit('chat', {'persona_id': app.persona_id, 'session_id': session_id,
                                'text': text, 'keep_loaded': True}, 'chat')
            app.turns = [*app.turns, {'role': 'user', 'content': text}]
        except CyToolError as exc:
            app.error = str(exc)

    if app.prompt_preview:
        imgui.begin_child('preview', (0, 120), imgui.ChildFlags_.borders)
        raw().text_wrapped(app.prompt_preview)
        imgui.end_child()
        if widgets.button('Hide the preview'):
            app.prompt_preview = ''

    if app.result.get('voiceError'):
        raw().text_wrapped(tr('Voice: ') + app.result['voiceError'])


# The delivery marks under a line, by kind (see personarp.marks.KINDS).
MARK_CAPTIONS = {'tone': 'tone', 'emotion': 'emotion', 'pause': 'pause', 'rate': 'rate',
                 'volume': 'volume', 'emphasis': 'emphasis', 'sound': 'sound'}

# What the proposal can fill, as the Section menu shows it.
TARGET_CAPTIONS = {
    'sheet': 'The whole sheet', 'identity': 'Identity', 'appearance': 'Appearance',
    'personality': 'Personality', 'speech': 'Speech', 'background': 'Background',
    'state': 'Current state', 'memory': 'Memory', 'media': 'Visual direction',
    'dialogues': 'Example dialogues', 'notes': 'Private notes',
    'world': 'The whole world', 'setting': 'Setting', 'locations': 'Locations',
    'factions': 'Factions', 'rules': 'Laws of this world', 'history': 'Timeline',
    'glossary': 'Glossary', 'canon': 'Canon — what must stay true'}

SHOW_CHOICES = ['both', 'translation', 'original']
SHOW_CAPTIONS = ['Original and translation', 'Translation only', 'Original only']


def _translation_bar(app, persona):
    """Choose a language, translate the scene with a model of your choice, hear it."""
    options = app.translation
    if imgui.collapsing_header(tr('Translation and voice in other languages'),
                               raw().TreeNodeFlags_.default_open):
        imgui.begin_disabled(app.busy)
        choices = [language for language in LANGUAGES if language != own_language(app, persona)]
        if options.get('language') not in choices:
            options['language'] = 'English' if 'English' in choices else choices[0]
        widgets.combo(options, 'language', tr('Language'), choices,
                      [tr(language) for language in choices])

        installed = [entry for entry in app.models if entry.get('installed')]
        identifiers = [''] + [entry['id'] for entry in installed]
        captions = [tr("(the character's model)")] + [entry['name'] for entry in installed]
        current = options.get('model', '')
        index = identifiers.index(current) if current in identifiers else 0
        changed, index = imgui.combo(tr('Translation model'), index, captions)
        if changed:
            options['model'] = identifiers[index]
        widgets.combo(options, 'device', tr('Device'), ['', 'cuda', 'cpu'],
                      [tr('Automatic'), tr('NVIDIA GPU'), tr('CPU')])
        widgets.checkbox(options, 'character_only', tr("Only the character's lines"))
        widgets.combo(options, 'show', tr('Show'), SHOW_CHOICES,
                      [tr(caption) for caption in SHOW_CAPTIONS])
        _, options['context'] = imgui.input_text('Note for the translator (optional)',
                                                 options.get('context', ''))
        raw().text_disabled(tr('The world, its places and terms, how the character speaks, where '
                               'the scene stands and the lines just before are always given to '
                               'the model. Add here what they do not say.'))

        ready = bool(app.session_id and app.turns)
        imgui.begin_disabled(not ready)
        parameters = {'persona_id': app.persona_id, 'session_id': app.session_id,
                      'target_language': options['language'], 'llm_model': options.get('model', ''),
                      'device': options.get('device', ''),
                      'roles': 'assistant' if options.get('character_only') else 'all',
                      'context': (options.get('context') or '').strip()}
        if widgets.button('Translate the scene'):
            app.submit('translate', parameters, 'translate')
        imgui.same_line()
        if widgets.button('Translate everything again'):
            app.submit('translate', {**parameters, 'overwrite': True}, 'translate')
        imgui.end_disabled()
        imgui.end_disabled()
        if not ready:
            imgui.same_line()
            raw().text_disabled(tr('Play a scene first.'))
        raw().text_disabled(tr('Lines already translated are kept; only new lines are sent to '
                               'the model. The original text is never changed.'))
        raw().text_disabled(language_summary(app, persona, options['language'])
                            + tr('  — set it in Characters › Voice.'))
    return {'language': options.get('language', 'English'), 'show': options.get('show', 'both')}


def _turn_voice(app, index, turn, language, translated):
    """Speak this line, in its own language or in the translation, and replay what was kept."""
    imgui.begin_disabled(app.busy)
    if widgets.small_button('Speak'):
        app.submit('speak_turn', {'persona_id': app.persona_id, 'session_id': app.session_id,
                                  'turn': index}, 'speak_turn')
    kept = (turn.get('audio') or {}).get('file', '')
    if kept and Path(kept).is_file():
        imgui.same_line()
        if widgets.small_button('Play the take'):
            app.play_file(kept)
    _takes_row(app, index, turn, '')
    if translated.get('text'):
        if widgets.small_button(tr('Speak %s') % tr(IN_LANGUAGE[language]), 'primary'):
            app.submit('speak_turn', {'persona_id': app.persona_id,
                                      'session_id': app.session_id, 'turn': index,
                                      'language': language}, 'speak_turn')
        kept = (translated.get('audio') or {}).get('file', '')
        if kept and Path(kept).is_file():
            imgui.same_line()
            if widgets.small_button(tr('Play the take %s') % tr(IN_LANGUAGE[language])):
                app.play_file(kept)
        _takes_row(app, index, translated, language)
    imgui.end_disabled()


def _takes_row(app, index, place, language):
    """Earlier takes of this line stay: step through them, keep one, or put one in the trash."""
    everything = takes.listing(place)
    if not everything:
        return
    chosen = max(0, takes.chosen(place))
    target = {'persona_id': app.persona_id, 'session_id': app.session_id, 'turn': index,
              'language': language}
    suffix = '##takes-%d-%s' % (index, language or 'original')
    imgui.same_line()
    raw().text_disabled(tr('Take %d of %d') % (chosen + 1, len(everything)))
    if len(everything) > 1:
        imgui.same_line()
        imgui.begin_disabled(chosen == 0)
        if widgets.small_button('<' + suffix + '-previous'):
            app.submit('choose_take', {**target, 'take': chosen - 1}, 'choose_take')
        imgui.end_disabled()
        imgui.same_line()
        imgui.begin_disabled(chosen >= len(everything) - 1)
        if widgets.small_button('>' + suffix + '-next'):
            app.submit('choose_take', {**target, 'take': chosen + 1}, 'choose_take')
        imgui.end_disabled()
    imgui.same_line()
    if widgets.small_button(tr('Trash this take') + suffix + '-trash', 'danger'):
        app.submit('remove_take', {**target, 'take': chosen}, 'remove_take')


# -------------------------------------------------------------------- characters

def _identity(app, persona):
    changed = widgets.text_field(persona, 'name', 'Name')
    changed |= widgets.text_field(persona, 'pronouns', 'Pronouns')
    changed |= widgets.text_field(persona, 'age', 'Age')
    changed |= widgets.text_field(persona, 'species', 'Species or kind')
    changed |= widgets.multiline(persona, 'summary', tr('Pitch — two lines that place them'), 44)
    changed |= widgets.string_list(persona, 'aliases', tr('Other names'))
    changed |= widgets.string_list(persona, 'tags', tr('Tags'))
    world_id, picked = widgets.picker(tr('Shared world'), persona.get('world_id', ''), app.worlds,
                                      '(no world)')
    if picked:
        persona['world_id'] = world_id
        changed = True
    raw().text_disabled(tr('The world carries the lore every character in it shares.'))
    changed |= widgets.checkbox(persona, 'enabled', 'Play this sheet in character')
    changed |= widgets.multiline(persona, 'notes', tr('Private notes (never sent to the model)'), 44)
    return changed


def _appearance(app, persona):
    changed = bool(reference_photographs(app, persona))
    picture_viewer(app, height=300.0)
    imgui.separator_text(tr('Written appearance'))
    branch = persona['appearance']
    changed |= widgets.multiline(branch, 'summary', tr('At a glance'), 44)
    for key, caption in (('build', 'Build and height'), ('face', 'Face'), ('hair', 'Hair'),
                         ('eyes', 'Eyes'), ('skin', 'Skin'), ('age_reading', 'Apparent age')):
        changed |= widgets.text_field(branch, key, tr(caption))
    for key, caption in (('outfit', 'Usual outfit'), ('marks', 'Scars, tattoos, marks'),
                         ('accessories', 'Accessories')):
        changed |= widgets.multiline(branch, key, tr(caption), 40)
    changed |= widgets.string_list(
        branch, 'visual_tags', tr('Visual tags'),
        'Short tags reused word for word in every image prompt. This is what keeps the '
        'character recognisable between two pictures.')
    changed |= widgets.string_list(branch, 'negative_tags', tr('Never depict'))
    changed |= widgets.multiline(branch, 'style_reference', tr('Rendering style'), 40)
    return changed


def _personality(persona):
    branch = persona['personality']
    changed = widgets.multiline(branch, 'summary', tr('In one sentence'), 40)
    for key, caption in (('traits', 'Traits'), ('values', 'Values'), ('desires', 'Wants'),
                         ('fears', 'Fears'), ('flaws', 'Flaws'), ('quirks', 'Quirks and habits')):
        changed |= widgets.string_list(branch, key, tr(caption))
    for key, caption in (('humour', 'Sense of humour'), ('temperament', 'Temperament'),
                         ('moral_compass', 'Moral compass')):
        changed |= widgets.multiline(branch, key, tr(caption), 40)
    return changed


def _speech(persona):
    branch = persona['speech']
    changed = widgets.multiline(branch, 'style', tr('Speaking style'), 44)
    for key, caption in (('register', 'Register'), ('accent', 'Accent')):
        changed |= widgets.text_field(branch, key, tr(caption))
    changed |= widgets.multiline(branch, 'vocabulary', tr('Vocabulary and imagery'), 40)
    for key, caption in (('verbal_tics', 'Verbal tics'), ('catchphrases', 'Catchphrases'),
                         ('languages', 'Languages spoken')):
        changed |= widgets.string_list(branch, key, tr(caption))
    changed |= widgets.multiline(branch, 'narration_style', tr('Narration style'), 40)
    changed |= widgets.multiline(branch, 'example_dialogues', tr('Example dialogues'), 120)
    return changed


def _background(persona):
    branch = persona['background']
    changed = widgets.text_field(branch, 'occupation', tr('Occupation or role'))
    changed |= widgets.multiline(branch, 'origin', tr('Origin'), 44)
    changed |= widgets.multiline(branch, 'story', tr('Life story'), 120)
    changed |= widgets.string_list(branch, 'skills', tr('Skills'))
    changed |= widgets.string_list(branch, 'possessions', tr('Notable possessions'))
    changed |= widgets.string_list(branch, 'factions', tr('Factions and affiliations'))
    changed |= widgets.multiline(branch, 'secrets', tr('Secrets'), 60)
    raw().text_disabled(tr('Secrets are given to the model as known but unspoken. They are not '
                           'sent to the scene describer.'))
    return changed


def _state_and_memory(app, persona):
    branch = persona['state']
    imgui.separator_text(tr('Right now — this is what evolves'))
    changed = widgets.multiline(branch, 'scenario', tr('Scene in progress'), 60)
    for key, caption in (('location', 'Location'), ('time', 'Time in fiction'), ('mood', 'Mood'),
                         ('energy', 'Physical condition'), ('outfit_now', 'Currently wearing')):
        changed |= widgets.text_field(branch, key, tr(caption))
    changed |= widgets.string_list(branch, 'goals', tr('Immediate goals'))
    changed |= widgets.string_list(branch, 'tensions', tr('Open tensions'))
    if branch.get('updated'):
        raw().text_disabled(tr('Last change: ') + branch['updated'])

    memory = persona['memory']
    imgui.separator_text(tr('Memory'))
    raw().text_disabled(tr('Memory stays explicit: nothing is taken from a conversation unless '
                           'you put it here.'))
    changed |= widgets.string_list(memory, 'facts', tr('Persistent facts'))
    changed |= widgets.dictionary_list(memory, 'episodes', tr('Remembered episodes'),
                                       [('when', tr('When'), False),
                                        ('summary', tr('What happened'), True)], 140)
    return changed


def _relations(app, persona):
    imgui.separator_text(tr('Relationships'))
    raw().text_disabled(tr('How this character feels about the others, injected into every reply.'))
    others = [entry for entry in app.personas if entry['id'] != persona.get('id')]
    changed = False
    removed = -1
    for index, relation in enumerate(list(persona.get('relationships') or [])):
        imgui.push_id('relation-%d' % index)
        target, picked = widgets.picker(tr('Other character'), relation.get('persona_id', ''),
                                        others, '(not in the library)')
        if picked:
            relation['persona_id'] = target
            match = next((o for o in others if o['id'] == target), None)
            if match:
                relation['name'] = match.get('name', target)
            changed = True
        changed |= widgets.text_field(relation, 'name', tr('Name as known'))
        changed |= widgets.text_field(relation, 'type', tr('Kind of bond'))
        changed |= widgets.text_field(relation, 'label', tr('Calls them'))
        changed |= widgets.slider_float(relation, 'sentiment', tr('Feeling'), -1.0, 1.0)
        changed |= widgets.slider_float(relation, 'trust', tr('Trust'), 0.0, 1.0)
        changed |= widgets.checkbox(relation, 'known', tr('They have met'))
        changed |= widgets.multiline(relation, 'history', tr('Shared history'), 40)
        changed |= widgets.multiline(relation, 'tension', tr('Current tension'), 40)
        changed |= widgets.multiline(relation, 'secret', tr('Kept from them'), 40)
        if widgets.button('Remove this bond'):
            removed = index
        imgui.same_line()
        if widgets.button('Write the mirror bond on their sheet'):
            try:
                app.call('set_relation', {'persona_id': persona['id'], 'relation': relation,
                                          'mirror': True})
                app.notice = 'Mirror bond written.'
                app.load_persona()
            except CyToolError as exc:
                app.error = str(exc)
        imgui.separator()
        imgui.pop_id()
    if removed >= 0:
        persona['relationships'].pop(removed)
        changed = True
    if widgets.button('Add a relationship'):
        persona.setdefault('relationships', []).append(
            {'persona_id': '', 'name': '', 'type': '', 'sentiment': 0.0, 'trust': 0.5})
        changed = True
    return changed


def _media(app, persona):
    branch = persona['media']
    changed = widgets.checkbox(branch, 'enabled', tr('Describe the shot with every reply'))
    raw().text_wrapped(tr('The description is returned as structured JSON for an image or video '
                          'tool. This Tool describes; it does not render.'))
    changed |= widgets.combo(branch, 'mode', tr('How it is produced'), ['director', 'inline'],
                             ['Second constrained pass (reliable)', 'Same reply (one generation)'])
    changed |= widgets.combo(branch, 'detail', tr('Detail'), ['minimal', 'standard', 'full'])
    installed = [entry for entry in app.models if entry.get('installed')]
    identifiers = [''] + [entry['id'] for entry in installed]
    captions = [tr('(same model as the conversation)')] + [entry['name'] for entry in installed]
    current = branch.get('director_model', '')
    index = identifiers.index(current) if current in identifiers else 0
    picked, index = imgui.combo(tr('Model used for the description'), index, captions)
    if picked:
        branch['director_model'] = identifiers[index]
        changed = True
    raw().text_disabled(tr('A larger model usually writes better shot descriptions than a small '
                           'roleplay model.'))
    changed |= widgets.text_field(branch, 'default_shot', tr('Default framing'))
    changed |= widgets.multiline(branch, 'motion_style', tr('Movement style'), 40)
    changed |= widgets.multiline(branch, 'camera_notes', tr('Camera notes'), 40)
    changed |= widgets.slider_float(branch, 'duration_seconds', tr('Clip length (s)'), 1.0, 60.0)
    changed |= widgets.text_field(branch, 'aspect_ratio', tr('Aspect ratio'))
    changed |= widgets.string_list(branch, 'extra_targets', tr('Extra rendering targets'),
                                   'Names of forms a downstream tool expects. The describer '
                                   'fills one entry per name under "renderings".')
    return changed


def _voice(app, persona):
    branch = persona['voice']
    voices = [{'id': v['id'], 'name': '%s (%.0fs)' % (v['name'], v['seconds'])}
              for v in getattr(app, 'voices', [])]
    chosen, picked = widgets.picker(tr('Stable voice'), branch.get('voice_id', ''), voices,
                                    '(no stable voice — a preset or a description is used)')
    changed = False
    if picked:
        branch['voice_id'] = chosen
        changed = True
    raw().text_disabled(tr('A stable voice is cloned from one recording, so every line of this '
                           'character sounds the same. Create one in the Voice tab.'))
    if branch.get('voice_id'):
        # Qwen3-TTS clones take no written instruction at all; saying so here avoids a
        # direction field that seems to do something and does nothing.
        raw().text_disabled(tr('A cloned voice reproduces its take: the standing direction and '
                               'the [tone:] marks only steer invented and preset voices. Pauses '
                               'apply to every voice.'))
    changed |= widgets.checkbox(branch, 'enabled', tr('Speak the replies'))
    changed |= widgets.checkbox(branch, 'annotations',
                                tr('Let the character write [tone:] and [pause:] marks'))
    changed |= widgets.checkbox(branch, 'speak_narration', tr('Also speak *stage directions*'))
    raw().text_disabled(tr('The scene description is never spoken, whatever these say.'))
    changed |= widgets.checkbox(branch, 'use_persona_style',
                                tr('Derive the delivery from the sheet and the scene'))
    changed |= widgets.combo(branch, 'language', tr('Spoken language'),
                             ['Auto', 'French', 'English', 'Spanish', 'German', 'Italian',
                              'Portuguese', 'Russian', 'Chinese', 'Japanese', 'Korean'])
    changed |= widgets.combo(branch, 'delivery', tr('Playback'), ['paragraphs', 'complete'],
                             ['Paragraph by paragraph', 'Whole take at once'])
    imgui.separator_text(tr('Speed and pitch'))
    changed |= widgets.slider_float(branch, 'speed', tr('Speed'), 0.5, 2.0, '%.2fx')
    changed |= widgets.slider_float(branch, 'pitch', tr('Pitch (semitones)'), -12.0, 12.0, '%+.1f')
    if widgets.small_button(tr('Natural speed and pitch') + '##voice-neutral'):
        branch['speed'], branch['pitch'] = 1.0, 0.0
        changed = True
    raw().push_text_wrap_pos(0.0)                  # a long hint wraps at the window's edge
    raw().text_disabled(tr('Applied to every spoken line after the model, in scenes, batches '
                           'and translations; never to the take a stable voice is captured '
                           'from. A few semitones change the height of the voice, an octave '
                           'turns it into another voice.'))
    raw().pop_text_wrap_pos()
    changed |= widgets.multiline(branch, 'instruction', tr('Standing voice direction'), 50)
    if not branch.get('voice_id'):
        imgui.separator_text(tr('Without a stable voice'))
        changed |= widgets.multiline(branch, 'description', tr('Voice to invent'), 50)
        raw().text_disabled(tr('Filled in, this describes a voice for VoiceDesign. Empty, the '
                               'preset speaker below is used.'))
        changed |= widgets.combo(branch, 'speaker', tr('Preset speaker'),
                                 ['Ryan', 'Aiden', 'Vivian', 'Serena', 'Uncle_Fu', 'Dylan',
                                  'Eric', 'Ono_Anna', 'Sohee'])
    changed |= _voice_languages(app, persona)
    return changed


LANGUAGE_SOURCES = ['same', 'voice', 'design', 'preset']
LANGUAGE_SOURCE_CAPTIONS = ['The same voice', 'Another stable voice', 'An invented voice',
                            'A preset speaker']


def _voice_languages(app, persona):
    """One entry per language the character should sound different in."""
    branch = persona['voice']
    imgui.separator_text(tr('Other languages'))
    raw().text_wrapped(tr('How this character sounds when a translated line is spoken. Keep the '
                          'same voice — with its accent, or with only its timbre — or give the '
                          'language a voice of its own. A language with no entry keeps the '
                          'same voice and its accent.'))
    entries = [dict(entry) for entry in branch.get('languages') or []]
    own = own_language(app, persona)
    changed = False
    removed = -1
    voices = [{'id': v['id'], 'name': '%s (%s, %.0fs)' % (v['name'], tr(v.get('language') or 'Auto'),
                                                         v['seconds'])}
              for v in getattr(app, 'voices', [])]
    for index, entry in enumerate(entries):
        imgui.push_id('language-%d' % index)
        edited = False
        # A language already configured elsewhere cannot be picked twice.
        taken = {other.get('language') for position, other in enumerate(entries)
                 if position != index} | {own}
        choices = [language for language in LANGUAGES if language not in taken]
        if entry.get('language') not in choices:
            choices.insert(0, entry.get('language', 'English'))
        imgui.separator_text(tr(entry.get('language', 'English')))
        if entry.get('language') == own:
            imgui.text_colored(imgui.ImVec4(1, 0.7, 0.4, 1),
                               tr("This is the character's own language: this entry is ignored. "
                                  'Change the main voice above instead.'))
        edited |= widgets.combo(entry, 'language', tr('Language'), choices,
                                [tr(language) for language in choices])
        edited |= widgets.combo(entry, 'source', tr('Voice used'), LANGUAGE_SOURCES,
                                [tr(caption) for caption in LANGUAGE_SOURCE_CAPTIONS])
        source = entry.get('source', 'same')
        if source == 'same':
            edited |= widgets.combo(entry, 'accent', tr('Accent'), ['keep', 'native'],
                                    [tr("Keep the character's accent"),
                                     tr('Pronounce like a native speaker')])
            if branch.get('voice_id'):
                raw().text_disabled(tr('Keep: the clone continues the take itself, accent '
                                       'included. Native: only the timbre is taken from the '
                                       'take; the words are pronounced as the model says them.'))
            else:
                raw().text_disabled(tr('Without a stable voice, the accent is asked for in the '
                                       'voice direction.'))
        elif source == 'voice':
            chosen, picked = widgets.picker(tr('Stable voice for this language'),
                                            entry.get('voice_id', ''), voices, '(choose a voice)')
            if picked:
                entry['voice_id'] = chosen
                edited = True
            raw().text_disabled(tr('Capture one in the Voice tab with the take language set to '
                                   '%s and keep it as the voice of that language.')
                                % tr(entry.get('language', 'English')))
        elif source == 'design':
            edited |= widgets.multiline(entry, 'description', tr('Voice to invent'), 44)
            raw().text_disabled(tr('For example: a man in his forties from London, low and dry, '
                                   'slow delivery.'))
        else:
            edited |= widgets.combo(entry, 'speaker', tr('Preset speaker'),
                                    ['Ryan', 'Aiden', 'Vivian', 'Serena', 'Uncle_Fu', 'Dylan',
                                     'Eric', 'Ono_Anna', 'Sohee'])
        if source in ('design', 'preset') or (source == 'same' and not branch.get('voice_id')):
            edited |= widgets.multiline(entry, 'instruction', tr('Direction for this language'), 40)
        _, seed = imgui.input_int(tr('Seed (-1 keeps the main voice seed)'),
                                  int(entry.get('seed', -1)))
        if seed != entry.get('seed', -1):
            entry['seed'] = max(-1, seed)
            edited = True
        if widgets.small_button('Remove this language'):
            removed = index
        imgui.pop_id()
        if edited:
            entries[index] = entry
            changed = True
    if removed >= 0:
        entries.pop(removed)
        changed = True

    free = [language for language in LANGUAGES
            if language not in {entry.get('language') for entry in entries} | {own}]
    if free:
        state = getattr(app, 'new_language', None)
        if state not in free:
            state = 'English' if 'English' in free else free[0]
        _, position = imgui.combo('##new-language', free.index(state),
                                  [tr(language) for language in free])
        app.new_language = free[position]
        imgui.same_line()
        if widgets.button('Add a language'):
            entries.append(normalize_language_voice({'language': app.new_language}))
            changed = True
    if changed:
        branch['languages'] = entries
    return changed


def _generation(app, persona):
    branch = persona['generation']
    installed = [entry for entry in app.models if entry.get('installed')]
    identifiers = [entry['id'] for entry in installed] or [branch.get('llm_model', 'nymphaea')]
    captions = [entry['name'] for entry in installed] or identifiers
    current = branch.get('llm_model', '')
    index = identifiers.index(current) if current in identifiers else 0
    picked, index = imgui.combo(tr('Conversation model'), index, captions)
    changed = False
    if picked:
        branch['llm_model'] = identifiers[index]
        changed = True
    changed |= widgets.combo(branch, 'device', tr('Device'), ['cpu', 'cuda'], ['CPU', 'NVIDIA GPU'])
    changed |= widgets.multiline(branch, 'system_prompt', tr('System prompt'), 70)
    changed |= widgets.multiline(branch, 'behaviour_rules', tr('Behaviour rules'), 50)
    changed |= widgets.text_field(branch, 'language', tr('Reply language'))
    changed |= widgets.slider_float(branch, 'temperature', tr('Creativity'), 0.0, 2.0)
    changed |= widgets.slider_float(branch, 'top_p', tr('Top-p'), 0.0, 1.0)
    changed |= widgets.slider_float(branch, 'repeat_penalty', tr('Repetition penalty'), 0.5, 2.0)
    changed |= widgets.slider_int(branch, 'response_length', tr('Reply length (tokens)'), 16, 4096)
    changed |= widgets.slider_int(branch, 'threads', tr('CPU threads'), 1, 64)
    changed |= widgets.slider_int(branch, 'context_budget', tr('Context budget (characters)'),
                                 1024, 32768)
    raw().text_disabled(tr('The sheet, the world and the cast get 70 % of this budget; the rest '
                           'is kept for the conversation. Preview the prompt to see what was '
                           'left out.'))
    changed |= widgets.checkbox(branch, 'stay_in_character', tr('Stay in character'))
    changed |= widgets.checkbox(branch, 'allow_narration', tr('Allow narration'))
    _, seed = imgui.input_int(tr('Seed (-1 random)'), int(branch.get('seed', -1)))
    if seed != branch.get('seed'):
        branch['seed'] = max(-1, seed)
        changed = True
    return changed


def characters(app):
    imgui.begin_disabled(app.busy)
    if widgets.button('New character'):
        try:
            outputs = app.call('create_persona', {'name': tr('New character')})
            app.refresh_library()
            app.select_persona(outputs['id'])
        except CyToolError as exc:
            app.error = str(exc)
    imgui.same_line()
    if widgets.button('Duplicate') and app.persona_id:
        try:
            outputs = app.call('duplicate_persona', {'persona_id': app.persona_id})
            app.refresh_library()
            app.select_persona(outputs['id'])
        except CyToolError as exc:
            app.error = str(exc)
    imgui.same_line()
    if widgets.button('Save') and app.persona:
        app.save_persona()
    imgui.same_line()
    if widgets.button('Move to trash') and app.persona_id:
        try:
            app.call('remove_persona', {'persona_id': app.persona_id})
            app.notice = 'Moved to data/personas/.trash — nothing was deleted.'
            app.persona_id = ''
            app.refresh_library()
        except CyToolError as exc:
            app.error = str(exc)
    imgui.end_disabled()

    if app.persona is None:
        raw().text_disabled(tr('No character selected.'))
        return
    if app.dirty:
        raw().text_disabled(tr('Unsaved changes.'))

    persona = app.persona
    changed = False
    if imgui.begin_tab_bar('sheet'):
        for caption, drawer in (
                ('Identity', lambda: _identity(app, persona)),
                ('Appearance', lambda: _appearance(app, persona)),
                ('Personality', lambda: _personality(persona)),
                ('Speech', lambda: _speech(persona)),
                ('Background', lambda: _background(persona)),
                ('State & memory', lambda: _state_and_memory(app, persona)),
                ('Relationships', lambda: _relations(app, persona)),
                ('Visual direction', lambda: _media(app, persona)),
                ('Voice', lambda: _voice(app, persona)),
                ('Model', lambda: _generation(app, persona))):
            flags = raw().TabItemFlags_.set_selected if SHEET_TAB == caption else 0
            opened, _ = imgui.begin_tab_item(caption, None, flags)
            if opened:
                # Use the height the window has, keeping room for the revision row and the
                # audio player, rather than a fixed 430 px that left half the window empty.
                row = raw().get_frame_height_with_spacing()
                player = getattr(app, 'player', None)
                reserve = row * 2 + (row * 3 if player is not None and player.loaded else 0)
                height = max(430.0, raw().get_content_region_avail().y - reserve)
                imgui.begin_child('sheet-body', (0, height), imgui.ChildFlags_.borders)
                changed |= bool(drawer())
                if SHEET_BOTTOM:
                    raw().set_scroll_y(raw().get_scroll_max_y())
                imgui.end_child()
                imgui.end_tab_item()
        imgui.end_tab_bar()
    if changed:
        app.dirty = True

    imgui.separator()
    if widgets.button('Revisions') and app.persona_id:
        try:
            app.notice = 'Revisions: ' + ', '.join(
                str(r['revision']) for r in app.call('persona_revisions',
                                                     {'persona_id': app.persona_id})['revisions'])
        except CyToolError as exc:
            app.error = str(exc)
    imgui.same_line()
    _, app.restore_revision = imgui.input_int(tr('Restore revision'),
                                              getattr(app, 'restore_revision', 1))
    imgui.same_line()
    if widgets.button('Restore') and app.persona_id:
        try:
            app.call('restore_persona', {'persona_id': app.persona_id,
                                         'revision': max(0, app.restore_revision)})
            app.load_persona()
            app.notice = 'Revision restored as a new revision.'
        except CyToolError as exc:
            app.error = str(exc)


# ------------------------------------------------------------------------ worlds

def worlds(app):
    imgui.begin_disabled(app.busy)
    if widgets.button('New world'):
        try:
            outputs = app.call('create_world', {'name': tr('New world')})
            app.refresh_library_names()
            app.world = normalize_world(outputs['world'])
            app.notice = 'World created: ' + outputs['id']
        except CyToolError as exc:
            app.error = str(exc)
    imgui.same_line()
    if widgets.button('Save world') and app.world:
        app.save_world()
    imgui.end_disabled()

    current = (app.world or {}).get('id', '')
    chosen, picked = widgets.picker(tr('World'), current, app.worlds, '(none)')
    if picked:
        try:
            app.flush()
            app.world = normalize_world(app.call('get_world', {'world_id': chosen})['world']) \
                if chosen else None
        except CyToolError as exc:
            app.error = str(exc)
    if app.world is None:
        raw().text_disabled(tr('A world holds the lore shared by several characters: places, '
                               'factions, laws, timeline and what must stay true.'))
        return

    world = app.world
    imgui.begin_child('world-body', (0, 470), imgui.ChildFlags_.borders)
    changed = widgets.text_field(world, 'name', tr('Name'))
    changed |= widgets.multiline(world, 'summary', tr('Pitch'), 44)
    changed |= widgets.text_field(world, 'genre', tr('Genre'))
    changed |= widgets.text_field(world, 'tone', tr('Tone'))
    changed |= widgets.text_field(world, 'era', tr('Era'))
    changed |= widgets.text_field(world, 'language', tr('Default language'))
    changed |= widgets.multiline(world, 'setting', tr('Setting'), 110)
    changed |= widgets.dictionary_list(world, 'locations', tr('Locations'),
                                       [('name', tr('Name'), False),
                                        ('description', tr('Description'), True)])
    changed |= widgets.dictionary_list(world, 'factions', tr('Factions'),
                                       [('name', tr('Name'), False),
                                        ('description', tr('Description'), True),
                                        ('stance', tr('Stance'), False)])
    changed |= widgets.dictionary_list(world, 'rules', tr('Laws of this world'),
                                       [('name', tr('Name'), False),
                                        ('description', tr('How it works'), True)])
    changed |= widgets.dictionary_list(world, 'history', tr('Timeline'),
                                       [('when', tr('When'), False),
                                        ('what', tr('What happened'), True)])
    changed |= widgets.dictionary_list(world, 'glossary', tr('Glossary'),
                                       [('term', tr('Term'), False),
                                        ('meaning', tr('Meaning'), True)])
    changed |= widgets.multiline(world, 'canon', tr('Canon — what must stay true'), 70)
    changed |= widgets.multiline(world, 'forbidden',
                                 tr('Out of bounds — what never happens here'), 50)
    changed |= widgets.multiline(world, 'narration_style', tr('House narration style'), 40)
    changed |= widgets.multiline(world, 'visual_style', tr('House visual style'), 40)
    raw().text_disabled(tr('The visual style is merged into every image and video description of '
                           'the characters in this world.'))
    _term_translations(app, world)
    if changed:
        app.world_dirty = True
    imgui.end_child()
    members = [entry['name'] for entry in app.personas if entry.get('world_id') == world.get('id')]
    raw().text_wrapped(tr('Cast: ') + (', '.join(members) or tr('nobody yet')))


def _term_translations(app, world):
    """How the places, factions and terms of this world are rendered in each language.

    Filled by the translator the first time a term appears; what you write here is kept and
    never replaced. Saved on its own, through set_term_translations.
    """
    smoke = '--smoke-open' in sys.argv            # screenshots of this section, in tests
    if smoke:
        raw().set_next_item_open(True)
    if not imgui.collapsing_header(tr('Translated terms')):
        return
    if smoke:
        raw().set_scroll_here_y(0.0)
    raw().text_wrapped(tr('Every translation renders these the same way. The translator fills '
                          'in a term the first time a scene mentions it; correct it here and '
                          'your rendering is kept for good. Leave a rendering empty to let the '
                          'translator render it again.'))
    state = app.__dict__.setdefault('term_editor', {'language': 'English', 'drafts': {}})
    choices = list(LANGUAGES)
    index = choices.index(state['language']) if state['language'] in choices else 0
    changed, index = imgui.combo(tr('Language') + '##terms', index, [tr(l) for l in choices])
    if changed:
        state['language'], state['drafts'] = choices[index], {}
    language = state['language']
    table = (world.get('term_translations') or {}).get(language) or {}
    terms = translation_module.world_terms(world)
    if not terms:
        raw().text_disabled(tr('This world has no place, faction or glossary term yet.'))
        return
    for item in terms:
        imgui.push_id('term-' + item['term'])
        entry = table.get(item['term']) or {}
        value = state['drafts'].get(item['term'], entry.get('text', ''))
        edited, value = imgui.input_text('##rendering', value)
        if edited:
            state['drafts'][item['term']] = value
        imgui.same_line()
        raw().text_unformatted('%s  (%s)' % (item['term'], tr(item['kind'])))
        imgui.same_line()
        if item['term'] in state['drafts']:
            imgui.text_colored(imgui.ImVec4(1.0, 0.75, 0.35, 1.0), tr('modified'))
        elif entry.get('source') == 'person':
            raw().text_disabled(tr('yours'))
        elif entry.get('text'):
            raw().text_disabled(tr('by %s') % (entry.get('model') or tr('the model')))
        else:
            raw().text_disabled(tr('not rendered yet'))
        imgui.pop_id()
    imgui.begin_disabled(app.busy or not state['drafts'])
    if widgets.button('Save the terms'):
        _save_terms(app, world, language, [{'term': term, 'text': text}
                                           for term, text in state['drafts'].items()])
        state['drafts'] = {}
    imgui.end_disabled()
    imgui.same_line()
    models_rendered = [term for term, entry in table.items() if entry.get('source') == 'model']
    imgui.begin_disabled(app.busy or not models_rendered)
    if widgets.button('Forget what the translator rendered'):
        _save_terms(app, world, language, [{'term': term, 'text': ''} for term in models_rendered])
        state['drafts'] = {}
    imgui.end_disabled()


def _save_terms(app, world, language, terms):
    try:
        app.call('set_term_translations', {'world_id': world['id'], 'language': language,
                                           'terms': terms}, flush=False)
        fresh = app.call('get_world', {'world_id': world['id']}, flush=False)['world']
        # Only the lexicon is taken from disk: other edits of the world stay as they are.
        world['term_translations'] = fresh.get('term_translations') or {}
        app.notice = tr('Terms saved (%d).') % len(terms)
    except CyToolError as exc:
        app.error = str(exc)


# --------------------------------------------------------------------- assistant

def assistant(app):
    """Two ways to use the assistant: talk about it first, then ask for a sheet."""
    if imgui.begin_tab_bar('assistant-modes'):
        opened, _ = imgui.begin_tab_item('Discussion')
        if opened:
            discussion(app)
            imgui.end_tab_item()
        opened, _ = imgui.begin_tab_item('Proposal')
        if opened:
            _proposal(app)
            imgui.end_tab_item()
        imgui.end_tab_bar()


def _proposal(app):
    raw().text_wrapped(tr('Ask for a sheet, a world, or one section of either. The assistant does '
                          'not play the character and writes nothing until you apply it.'))
    targets = ['sheet', 'identity', 'appearance', 'personality', 'speech', 'background', 'state',
               'memory', 'media', 'dialogues', 'notes']
    world_targets = ['world', 'setting', 'locations', 'factions', 'rules', 'history', 'glossary',
                     'canon']
    kinds = ['persona', 'world']
    index = kinds.index(app.proposal_kind) if app.proposal_kind in kinds else 0
    changed, index = imgui.combo(tr('Write for'), index, [tr('A character'), tr('A world')])
    if changed:
        app.proposal_kind = kinds[index]
        app.proposal_target = 'sheet' if app.proposal_kind == 'persona' else 'world'
    choices = targets if app.proposal_kind == 'persona' else world_targets
    position = choices.index(app.proposal_target) if app.proposal_target in choices else 0
    changed, position = imgui.combo(tr('Section'), position,
                                    [tr(TARGET_CAPTIONS.get(choice, choice)) for choice in choices])
    if changed:
        app.proposal_target = choices[position]

    # The assistant has no sheet of its own, so its model and device are chosen here.
    settings = getattr(app, 'author_settings', None)
    if settings is None:
        settings = app.author_settings = {'llm_model': '', 'device': '', 'response_length': 2048}
    installed = [entry for entry in app.models if entry.get('installed')]
    identifiers = [''] + [entry['id'] for entry in installed]
    captions = [tr('(the model of the selected character)')] + [e['name'] for e in installed]
    current = settings['llm_model']
    index = identifiers.index(current) if current in identifiers else 0
    picked, index = imgui.combo(tr('Model used to write'), index, captions)
    if picked:
        settings['llm_model'] = identifiers[index]
    raw().text_disabled(tr('Writing a sheet is a structured task. A larger, more '
                           'instruction-following model does it better than a small roleplay '
                           'one, which is what plays the character.'))
    widgets.combo(settings, 'device', tr('Device'), ['', 'cuda', 'cpu'],
                  [tr('(the device of the character)'), tr('NVIDIA GPU'), tr('CPU')])
    widgets.slider_int(settings, 'response_length', tr('Maximum proposal length (tokens)'),
                       256, 4096)
    if not installed:
        raw().text_disabled(tr('No model is installed yet; install one in Models.'))

    threads = [{'id': t['id'], 'name': '%s (%d)' % (t['title'] or 'Discussion', t['turns'])}
               for t in app.threads if t['turns']]
    chosen, picked = widgets.picker(tr('Build on a discussion'),
                                    getattr(app, 'author_thread', ''), threads, '(none)')
    if picked:
        app.author_thread = chosen
    if threads:
        raw().text_disabled(tr('What was said in that discussion is handed to the assistant '
                               'along with your request.'))

    guide = getattr(app, 'author_image', None)
    if guide is None:
        guide = app.author_image = {'image': ''}
    widgets.text_field(guide, 'image',
                       tr('Reference picture (full path, or a file in data/inputs)'))
    raw().text_disabled(tr('It is read by the vision model first, and what it shows is handed '
                           'to the assistant as the appearance to work from.'))

    imgui.text(tr('What do you want?'))
    _, app.author_request = imgui.input_text_multiline('##request', app.author_request, (-1, 80))
    imgui.begin_disabled(app.busy or not app.author_request.strip())
    if widgets.button('Ask'):
        app.submit('author', {'request': app.author_request, 'target': app.proposal_target,
                              'kind': app.proposal_kind, 'persona_id': app.persona_id,
                              'world_id': (app.world or {}).get('id', ''),
                              'language': (app.persona or {}).get('generation', {}).get(
                                  'language', 'Francais'),
                              'llm_model': settings['llm_model'], 'device': settings['device'],
                              'response_length': settings['response_length'],
                              'thread_id': getattr(app, 'author_thread', ''),
                              'image': guide['image'],
                              'keep_loaded': True}, 'author')
    imgui.end_disabled()
    if app.busy and app.purpose == 'author':
        imgui.same_line()
        raw().text_disabled(tr('Writing...'))

    if app.proposal is None:
        return
    imgui.separator_text(tr('Proposal'))
    body = app.proposal if isinstance(app.proposal, str) \
        else json.dumps(app.proposal, ensure_ascii=False, indent=2)
    imgui.begin_child('proposal', (0, 260), imgui.ChildFlags_.borders)
    edited, body = imgui.input_text_multiline('##proposal-body', body, (-1, -1))
    imgui.end_child()
    if edited:
        if isinstance(app.proposal, str):
            app.proposal = body
        else:
            try:
                app.proposal = json.loads(body)
                app.error = ''
            except ValueError as exc:
                app.error = 'Proposal is not valid JSON: ' + str(exc)
    imgui.begin_disabled(app.busy)
    if widgets.button('Apply to the selected character' if app.proposal_kind == 'persona'
                    else 'Apply to the selected world'):
        try:
            payload = {'target': app.proposal_target, 'kind': app.proposal_kind,
                       'proposal': app.proposal}
            if app.proposal_kind == 'persona':
                payload['persona_id'] = app.persona_id
            else:
                payload['world_id'] = (app.world or {}).get('id', '')
            outputs = app.call('apply_proposal', payload)
            app.notice = tr('Applied (revision %d).') % outputs['revision']
            app.proposal = None
            app.refresh_library()
        except CyToolError as exc:
            app.error = str(exc)
    imgui.same_line()
    if widgets.button('Discard'):
        app.proposal = None
    imgui.end_disabled()


# ------------------------------------------------------------------------ library

def library_tab(app):
    if imgui.begin_tab_bar('library-modes'):
        for caption, drawer in (('Examples', _examples), ('Pictures', library_gallery),
                                ('Export and import', _exchange), ('ComfyUI', comfyui_tab)):
            flags = raw().TabItemFlags_.set_selected if SHEET_TAB == caption else 0
            opened, _ = imgui.begin_tab_item(caption, None, flags)
            if opened:
                drawer(app)
                imgui.end_tab_item()
        imgui.end_tab_bar()


def _examples(app):
    """The example worlds shipped with the Tool, one click from the library."""
    if getattr(app, 'examples', None) is None:
        try:
            outputs = app.call('list_examples', flush=False)
            app.examples = outputs.get('examples', [])
            app.examples_folder = outputs.get('folder', '')
        except CyToolError as exc:
            app.error = str(exc)
            app.examples = []
    raw().text_wrapped(tr('Worlds ready to play, each with its cast. Importing one copies it into '
                          'your library: the example itself never changes, and a character you '
                          'already have is never overwritten.'))
    if widgets.button('Open the examples folder'):
        open_path(getattr(app, 'examples_folder', ''))
    imgui.same_line()
    if widgets.button('Refresh##examples'):
        app.examples = None
        return
    if not app.examples:
        raw().text_disabled(tr('No example found in app/examples.'))
        return
    height = max(300.0, raw().get_content_region_avail().y - raw().get_frame_height_with_spacing())
    imgui.begin_child('examples', (0, height), imgui.ChildFlags_.borders)
    for item in app.examples:
        imgui.push_id('example-' + item['id'])
        raw().separator_text(item['world'])
        raw().text_disabled(item.get('genre', ''))
        raw().text_wrapped(item.get('summary', ''))
        imgui.text(tr('Characters: ') + ', '.join(entry['name'] for entry in item['characters']))
        if item.get('voices'):
            raw().text_disabled(tr('%d stable voices included — they come in with the import.')
                                % item['voices'])
        if item.get('scenes'):
            raw().text_disabled(tr('Scenes to play from: ') + ', '.join(
                '%s (%d)' % (scene['title'], scene['lines']) for scene in item['scenes']))
        if item.get('imported'):
            imgui.text_colored(imgui.ImVec4(0.45, 0.85, 0.5, 1.0),
                               tr('Already in your library — importing it again makes copies.'))
        imgui.begin_disabled(app.busy)
        if widgets.button(tr('Import again') if item.get('imported') else tr('Import this world'),
                          'confirm'):
            app.submit('import_personas', {'file': item['file'], 'rename': True}, 'import')
        imgui.end_disabled()
        imgui.pop_id()
    imgui.end_child()


def _exchange(app):
    imgui.separator_text(tr('Export'))
    raw().text_wrapped(tr('An export is self-contained: the sheets, their world and their voice '
                          'descriptors, so a character can be carried to another machine.'))
    selection = getattr(app, 'export_selection', None)
    if selection is None:
        selection = app.export_selection = {}
    for entry in app.personas:
        checked = selection.get(entry['id'], entry['id'] == app.persona_id)
        _, checked = imgui.checkbox(entry['name'] + '##export-' + entry['id'], checked)
        selection[entry['id']] = checked
    _, app.export_audio = imgui.checkbox(tr('Include the reference recordings (produces a .zip)'),
                                         getattr(app, 'export_audio', False))
    _, app.export_scenes = imgui.checkbox(tr('Include their scenes (the words, not the takes)'),
                                          getattr(app, 'export_scenes', False))
    imgui.begin_disabled(app.busy)
    if widgets.button('Export the selection'):
        chosen = [identifier for identifier, on in selection.items() if on]
        if chosen:
            app.submit('export_personas', {'persona_ids': chosen,
                                           'include_audio': app.export_audio,
                                           'include_sessions': app.export_scenes}, 'export')
        else:
            app.error = 'Select at least one character.'
    imgui.same_line()
    if widgets.button('Open the exports folder'):
        open_path(EXPORTS)
    imgui.end_disabled()

    imgui.separator_text(tr('Import'))
    raw().text_wrapped(tr('Drop a bundle in data/inputs, or give its full path. An existing '
                          'character is never overwritten: a clash creates a new identifier.'))
    _, app.import_path = imgui.input_text(tr('Bundle file'), getattr(app, 'import_path', ''))
    imgui.begin_disabled(app.busy or not app.import_path.strip())
    if widgets.button('Import'):
        app.submit('import_personas', {'file': app.import_path, 'rename': True}, 'import')
    imgui.end_disabled()
    imgui.same_line()
    if widgets.button('Open data/inputs'):
        open_path(DATA / 'inputs')

    imgui.separator_text(tr('Scenes'))
    for entry in getattr(app, 'sessions', []):
        raw().text_disabled('%s — %d turns — %s' % (entry.get('title', entry['id']),
                                                    entry.get('turns', 0),
                                                    entry.get('modified', '')))


# ------------------------------------------------------------------------- models

def models_tab(app):
    imgui.begin_disabled(app.busy)
    if widgets.button('Refresh'):
        app.submit('list_models', {'verify': False}, 'list_models')
    imgui.same_line()
    if widgets.button('Verify the installed weights'):
        app.submit('list_models', {'verify': True}, 'list_models')
    imgui.same_line()
    if widgets.button('Unload the resident model'):
        app.submit('unload_model', {}, 'unload_model')
    imgui.end_disabled()

    engine = app.engine or {}
    imgui.separator_text(tr('Engine'))
    for key, caption in (('cpu', 'llama.cpp CPU'), ('cuda', 'NVIDIA CUDA')):
        info = engine.get(key) or {}
        raw().text_wrapped('%s: %s' % (tr(caption),
                                       tr('installed') if info.get('installed') else tr('absent')))
        if info.get('devices'):
            raw().text_disabled(info['devices'].strip().splitlines()[1]
                                if len(info['devices'].splitlines()) > 1 else info['devices'])
    imgui.begin_disabled(app.busy)
    if widgets.button('Install / repair the CUDA engine'):
        app.submit('install_cuda', {}, 'install_cuda')
    imgui.same_line()
    if widgets.button('Install / update the CPU engine'):
        app.submit('update', {'kind': 'engine', 'action': 'download'}, 'update')
    imgui.end_disabled()

    imgui.separator_text(tr('Conversation models'))
    free = (app.diagnosis.get('paths') or {}).get('freeBytes')
    if free:
        raw().text_disabled(tr('Free space: %.1f GB') % (free / 1e9))
    accepted = getattr(app, 'license_accept', None)
    if accepted is None:
        accepted = app.license_accept = {}
    imgui.begin_child('models', (0, 400), imgui.ChildFlags_.borders)
    for entry in app.models:
        imgui.push_id(entry['id'])
        state = tr('installed') if entry['installed'] else (
            tr('partly downloaded') if entry.get('presentBytes') else tr('not installed'))
        imgui.separator_text('%s — %s' % (entry['name'], state))
        raw().text_disabled('%.2f GB · %s · RAM %d GB · VRAM %d GB'
                            % (entry['sizeBytes'] / 1e9, entry['id'], entry.get('ramGiB', 0),
                               entry.get('vramGiB', 0)))
        if entry.get('notes'):
            raw().text_wrapped(entry['notes'])
        raw().text_wrapped(tr('Licence: ') + (entry.get('license') or tr('not declared')))
        if entry.get('source') and widgets.button('Official page and licence'):
            webbrowser.open(entry['source'])
        already = entry.get('licenseAccepted', False)
        checked = accepted.get(entry['id'], already)
        _, checked = imgui.checkbox(tr('I personally accept this licence'), checked)
        accepted[entry['id']] = checked
        imgui.begin_disabled(app.busy or not checked)
        if widgets.button('Download / resume' if not entry['installed'] else 'Repair / verify'):
            app.submit('install_llm', {'model': entry['id'], 'accept_license': True}, 'install_llm')
        imgui.end_disabled()
        imgui.pop_id()
    imgui.end_child()
    raw().text_wrapped(tr('Weights live in data/models/llm. A download can be cancelled and '
                          'resumed; nothing is marked installed before its SHA-256 matches.'))


# ------------------------------------------------------------------------ updates

def updates_tab(app):
    raw().text_wrapped(tr('The application, the engine and the weights are three separate '
                          'streams. Weights follow the Models tab. data/ is never replaced.'))
    _, app.updates['repository'] = imgui.input_text(tr('GitHub repository of this Tool '
                                                       '(owner/name)'),
                                                    app.updates.get('repository', ''))
    _, app.updates['auto_check'] = imgui.checkbox(tr('Check at startup'),
                                                  app.updates.get('auto_check', False))
    _, app.updates['auto_download'] = imgui.checkbox(tr('Download updates at startup'),
                                                     app.updates.get('auto_download', False))
    if widgets.button('Save these preferences'):
        app.persist()
        app.notice = 'Preferences saved.'
    if not app.updates.get('repository'):
        raw().text_disabled(tr('No repository is configured for this Tool, so the application '
                               'stream cannot be checked. The engine stream works without one.'))
    imgui.begin_disabled(app.busy)
    for kind, caption in (('engine', 'llama.cpp engine'), ('app', 'CyTools application')):
        imgui.separator_text(tr(caption))
        for action, button in (('check', 'Check'), ('download', 'Download'),
                               ('activate', 'Activate'), ('rollback', 'Roll back')):
            if action != 'check':
                imgui.same_line()
            if widgets.button(tr(button) + '##' + kind + action):
                app.submit('update', {'kind': kind, 'action': action,
                                      'repository': app.updates.get('repository', '')}, 'update')
    imgui.end_disabled()
    raw().text_wrapped(tr('A staged application is activated at the next launch, under a lock, '
                          'and the previous version is kept for a roll back. An update is '
                          'verified before activation; a published checksum is not a signature.'))


# --------------------------------------------------------------------- diagnostics

def diagnostics(app):
    imgui.begin_disabled(app.busy)
    if widgets.button('Run a diagnosis'):
        app.submit('diagnose_backend', {'verify': False}, 'diagnose_backend')
    imgui.same_line()
    if widgets.button('Deep check (SHA-256 of every model)'):
        app.submit('diagnose_backend', {'verify': True}, 'diagnose_backend')
    imgui.end_disabled()
    imgui.same_line()
    if widgets.button('Open the reports folder'):
        open_path(DATA / 'reports')
    body = json.dumps(app.diagnosis, ensure_ascii=False, indent=2) if app.diagnosis \
        else tr('Run a diagnosis to see models, engines, devices and paths.')
    imgui.begin_child('diagnosis', (0, 430), imgui.ChildFlags_.borders)
    imgui.input_text_multiline('##diagnosis-body', body, (-1, -1),
                               raw().InputTextFlags_.read_only)
    imgui.end_child()
    raw().text_wrapped(tr('The text above is selectable and copyable. See VALIDATION.md for what '
                          'has actually been executed on this machine.'))
