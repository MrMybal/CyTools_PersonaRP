"""The tabs of the desktop window.

Each panel edits state and submits operations; none of them talks to a model directly.
"""
import json
import sys
import webbrowser
from pathlib import Path

from cytools_core import CyToolError
import cyui
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
    if raw().tree_node_ex('##scene', 0, (cyui.icon.photo + '  ' if cyui.icons_available() else '')
                          + tr('Scene description') + (' — ' + summary if summary else '')):
        widgets.hint(tr('Data for an image or video tool. It is never read aloud.'))
        camera, setting = directive.get('camera') or {}, directive.get('setting') or {}
        rows = [(tr(caption), str(directive.get(key) or '')) for key, caption in SCENE_ROWS]
        rows.append((tr('Movement'), '\n'.join('%.1fs — %s' % (float(beat.get('at', 0)),
                                                               beat.get('action', ''))
                                               for beat in directive.get('motion') or [])))
        rows.append((tr('Camera'), ', '.join(x for x in (camera.get('shot'), camera.get('angle'),
                                                        camera.get('lens'), camera.get('movement'))
                                            if x)))
        rows.append((tr('Setting'), ', '.join(x for x in (setting.get('location'), setting.get('time'),
                                                         setting.get('weather'),
                                                         setting.get('lighting')) if x)))
        if cyui.begin_properties('##directive', 120.0):
            for caption, value in rows:
                if value:
                    cyui.property(caption)
                    raw().text_wrapped(value)
            for key, caption in (('image_prompt', 'Image prompt'), ('video_prompt', 'Video prompt'),
                                 ('negative_prompt', 'Negative prompt')):
                value = str((prompts or {}).get(key) or directive.get(key) or '')
                if value:
                    cyui.property(tr(caption))
                    raw().input_text_multiline('##' + key + identity, value, (-1, cyui.dp(46)),
                                               raw().InputTextFlags_.read_only)
            cyui.end_properties()
        payload = json.dumps({**directive, **(prompts or {})}, ensure_ascii=False, indent=2)
        if cyui.icon_text_button(cyui.icon.copy, tr('Copy the JSON'), 'ghost'):
            raw().set_clipboard_text(payload)
        cyui.tooltip(tr('Paste it into an image or video tool, or export the session.'))
        raw().tree_pop()
    imgui.pop_id()


def _scene_toolbar(app, persona):
    """Which scene is played, a new one, and the tools around it."""
    imgui.begin_disabled(app.busy)
    entries = getattr(app, 'sessions', [])
    identifiers = [entry['id'] for entry in entries]
    if entries:
        captions = ['%s (%d)' % (entry.get('title') or entry['id'], entry.get('turns', 0))
                    for entry in entries]
        index = identifiers.index(app.session_id) if app.session_id in identifiers else 0
        raw().set_next_item_width(cyui.dp(320.0))
        changed, index = raw().combo('##scene', index, captions)
        cyui.tooltip(tr('The scene being played'))
        if changed:
            app.session_id = identifiers[index]
            app.reload_conversation()
        imgui.same_line()
    if cyui.icon_text_button(cyui.icon.add, tr('New scene'), 'outline'):
        try:
            app.session_id = ''
            app.ensure_session()
            app.notice = 'New scene started.'
        except CyToolError as exc:
            app.error = str(exc)
    cyui.toolbar_separator()
    if widgets.icon_button(cyui.icon.view, 'Preview the prompt the model receives'):
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
    if widgets.icon_button(cyui.icon.folder, 'Open the scene folder'):
        open_path(DATA / 'sessions' / app.persona_id)
    imgui.end_disabled()
    imgui.same_line(0.0, cyui.dp(14.0))
    raw().align_text_to_frame_padding()
    cyui.badge((persona['generation'].get('llm_model') or '?') + ' · '
               + persona['generation'].get('device', 'cpu').upper())
    if persona['media'].get('enabled'):
        imgui.same_line()
        cyui.badge(tr('scene description on'), 'info')


def _transcript(app, persona, language, shown_mode, height):
    with cyui.scoped_color(raw().Col_.child_bg, cyui.palette().bg0):
        raw().begin_child('transcript', (0, height), raw().ChildFlags_.borders)
    if not app.turns and not (app.busy and app.purpose == 'chat'):
        widgets.empty('No line yet', 'Write a message below to start the scene.', cyui.icon.people)
    for index, turn in enumerate(app.turns):
        imgui.push_id('turn-%d' % index)
        user = turn.get('role') == 'user'
        cyui.space(4.0)
        cyui.overline((tr('You') if user else persona.get('name', 'Character')).upper(),
                      cyui.palette().textDim if user else 0)
        content = str(turn.get('content', ''))
        translated = ((turn.get('translations') or {}).get(language) or {})
        if shown_mode != 'translation' or not translated.get('text'):
            if not user:
                parsed = scene_module.split_reply(content)
                raw().text_wrapped(scene_module.strip_annotations(parsed['text']))
                marks = scene_module.parse_annotations(parsed['text'])
                if marks:
                    widgets.hint(tr('Delivery: ') + ', '.join(
                        '%s=%s' % (tr(MARK_CAPTIONS.get(m['kind'], m['kind'])), m['value'])
                        for m in marks))
            else:
                raw().text_wrapped(content)
        if shown_mode != 'original' and translated.get('text'):
            cyui.badge(tr(language), 'info')
            imgui.same_line()
            raw().text_wrapped(scene_module.strip_annotations(translated['text']))
            if translated.get('marksLost'):
                widgets.hint(tr('Marks lost in translation: ') + ' '.join(translated['marksLost']))
            if translated.get('termsMissed'):
                cyui.text_coloured(cyui.palette().warning,
                                   tr('Terms not kept: ') + '; '.join(translated['termsMissed']))
        if not user:
            _turn_voice(app, index, turn, language, translated)
            _draw_scene(turn.get('scene') or scene_module.split_reply(content)['scene'],
                        turn.get('prompts'), str(index))
        imgui.pop_id()
    if app.busy and app.purpose == 'chat':
        cyui.space(4.0)
        cyui.overline(persona.get('name', 'Character').upper())
        cyui.spinner('##writing', 6.0)
        imgui.same_line()
        cyui.text_faint(tr('Writing...'))
    raw().end_child()


def conversation(app):
    persona = app.persona
    if persona is None:
        widgets.empty('No character yet', 'Create one in Characters, or import an example world '
                      'from Library.', cyui.icon.contact)
        return
    _scene_toolbar(app, persona)
    cyui.space(4.0)
    options = _translation_bar(app, persona)
    language = options['language']
    shown_mode = options['show']

    # The scene takes the height the composer leaves.
    composer = cyui.dp(84.0) + raw().get_frame_height() * 2 + raw().get_text_line_height() \
        + raw().get_style().item_spacing.y * 4
    preview = cyui.dp(140.0) if app.prompt_preview else 0.0
    height = max(cyui.dp(160.0), raw().get_content_region_avail().y - composer - preview)
    _transcript(app, persona, language, shown_mode, height)

    if app.prompt_preview:
        if cyui.begin_card('##preview', '', 120.0):
            cyui.text_dim(tr('Prompt preview'))
            imgui.same_line()
            cyui.align_right(raw().get_frame_height())
            if widgets.icon_button(cyui.icon.close, 'Hide the preview'):
                app.prompt_preview = ''
            raw().text_wrapped(app.prompt_preview)
        cyui.end_card()

    cyui.text_faint(tr('Your message — Enter sends, Ctrl+Enter adds a line'))
    entered, app.draft = raw().input_text_multiline(
        '##composer', app.draft, (-1, cyui.dp(84.0)),
        raw().InputTextFlags_.enter_returns_true | raw().InputTextFlags_.ctrl_enter_for_new_line)
    send = entered and not raw().get_io().key_ctrl
    imgui.begin_disabled(app.busy)
    if cyui.icon_text_button(cyui.icon.send, tr('Send'), 'primary'):
        send = True
    imgui.same_line()
    # Dictation: the microphone is recorded here, then transcribed by Whisper like any file;
    # the words are added to the message, which is sent only when you send it.
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

    if app.result.get('voiceError'):
        cyui.callout('warning', tr('Voice: ') + app.result['voiceError'])


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
    choices = [language for language in LANGUAGES if language != own_language(app, persona)]
    if options.get('language') not in choices:
        options['language'] = 'English' if 'English' in choices else choices[0]
    if cyui.begin_section(tr('Translation and voice in other languages') + '###translation',
                          bool(app.translation.get('open'))):
        imgui.begin_disabled(app.busy)
        with widgets.properties('##translation-options'):
            widgets.combo(options, 'language', 'Language', choices, [tr(language) for language in choices])
            installed = [entry for entry in app.models if entry.get('installed')]
            identifiers = [''] + [entry['id'] for entry in installed]
            captions = [tr("(the character's model)")] + [entry['name'] for entry in installed]
            current = options.get('model', '')
            index = identifiers.index(current) if current in identifiers else 0
            cyui.property(tr('Translation model'))
            changed, index = raw().combo('##translation-model', index, captions)
            if changed:
                options['model'] = identifiers[index]
            widgets.combo(options, 'device', 'Device', ['', 'cuda', 'cpu'],
                          [tr('Automatic'), tr('NVIDIA GPU'), tr('CPU')])
            widgets.checkbox(options, 'character_only', "Only the character's lines")
            cyui.property(tr('Show'))
            index = SHOW_CHOICES.index(options.get('show', 'both')) if options.get('show') in SHOW_CHOICES else 0
            changed, index = cyui.segmented('##show', [tr(c) for c in SHOW_CAPTIONS], index, -1)
            if changed:
                options['show'] = SHOW_CHOICES[index]
            cyui.property(tr('Note for the translator (optional)'))
            _, options['context'] = raw().input_text('##translator-note', options.get('context', ''))
            widgets.hint(tr('The world, its places and terms, how the character speaks, where '
                            'the scene stands and the lines just before are always given to '
                            'the model. Add here what they do not say.'))
        ready = bool(app.session_id and app.turns)
        imgui.begin_disabled(not ready)
        parameters = {'persona_id': app.persona_id, 'session_id': app.session_id,
                      'target_language': options['language'], 'llm_model': options.get('model', ''),
                      'device': options.get('device', ''),
                      'roles': 'assistant' if options.get('character_only') else 'all',
                      'context': (options.get('context') or '').strip()}
        if cyui.icon_text_button(cyui.icon.globe, tr('Translate the scene'), 'outline'):
            app.submit('translate', parameters, 'translate')
        imgui.same_line()
        if widgets.button('Translate everything again', 'quiet'):
            app.submit('translate', {**parameters, 'overwrite': True}, 'translate')
        imgui.end_disabled()
        imgui.end_disabled()
        if not ready:
            imgui.same_line()
            raw().align_text_to_frame_padding()
            cyui.text_faint(tr('Play a scene first.'))
        widgets.hint(tr('Lines already translated are kept; only new lines are sent to '
                        'the model. The original text is never changed.'))
        widgets.hint(language_summary(app, persona, options['language'])
                     + tr('  — set it in Characters › Voice.'))
        app.translation['open'] = True
        cyui.end_section()
    else:
        app.translation['open'] = False
    return {'language': options.get('language', 'English'), 'show': options.get('show', 'both')}


def _turn_voice(app, index, turn, language, translated):
    """Speak this line, in its own language or in the translation, and replay what was kept."""
    imgui.begin_disabled(app.busy)
    if widgets.icon_button(cyui.icon.volume, 'Speak this line'):
        app.submit('speak_turn', {'persona_id': app.persona_id, 'session_id': app.session_id,
                                  'turn': index}, 'speak_turn')
    kept = (turn.get('audio') or {}).get('file', '')
    if kept and Path(kept).is_file():
        imgui.same_line()
        if widgets.icon_button(cyui.icon.play, 'Play the take'):
            app.play_file(kept)
    _takes_row(app, index, turn, '')
    if translated.get('text'):
        imgui.same_line(0.0, cyui.dp(16.0))
        if cyui.icon_text_button(cyui.icon.volume, tr('Speak %s') % tr(IN_LANGUAGE[language]), 'ghost'):
            app.submit('speak_turn', {'persona_id': app.persona_id,
                                      'session_id': app.session_id, 'turn': index,
                                      'language': language}, 'speak_turn')
        kept = (translated.get('audio') or {}).get('file', '')
        if kept and Path(kept).is_file():
            imgui.same_line()
            if cyui.icon_button(cyui.icon.play, tr('Play the take %s') % tr(IN_LANGUAGE[language])):
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
    imgui.push_id('takes-%d-%s' % (index, language or 'original'))
    imgui.same_line()
    raw().align_text_to_frame_padding()
    cyui.text_faint(tr('Take %d of %d') % (chosen + 1, len(everything)))
    if len(everything) > 1:
        imgui.same_line()
        imgui.begin_disabled(chosen == 0)
        if widgets.icon_button(cyui.icon.chevron_left, 'Previous take'):
            app.submit('choose_take', {**target, 'take': chosen - 1}, 'choose_take')
        imgui.end_disabled()
        imgui.same_line()
        imgui.begin_disabled(chosen >= len(everything) - 1)
        if widgets.icon_button(cyui.icon.chevron_right, 'Next take'):
            app.submit('choose_take', {**target, 'take': chosen + 1}, 'choose_take')
        imgui.end_disabled()
    imgui.same_line()
    if widgets.icon_button(cyui.icon.trash, 'Trash this take'):
        app.submit('remove_take', {**target, 'take': chosen}, 'remove_take')
    imgui.pop_id()


# -------------------------------------------------------------------- characters

PRESET_SPEAKERS = ['Ryan', 'Aiden', 'Vivian', 'Serena', 'Uncle_Fu', 'Dylan', 'Eric', 'Ono_Anna',
                   'Sohee']


def _identity(app, persona):
    widgets.section('Who they are')
    with widgets.properties('##identity'):
        changed = widgets.text_field(persona, 'name', 'Name')
        changed |= widgets.text_field(persona, 'pronouns', 'Pronouns')
        changed |= widgets.text_field(persona, 'age', 'Age')
        changed |= widgets.text_field(persona, 'species', 'Species or kind')
        changed |= widgets.multiline(persona, 'summary', 'Pitch — two lines that place them', 44)
        changed |= widgets.string_list(persona, 'aliases', 'Other names')
        changed |= widgets.string_list(persona, 'tags', 'Tags')
    widgets.section('Play')
    with widgets.properties('##identity-play'):
        world_id, picked = widgets.picker('Shared world', persona.get('world_id', ''), app.worlds,
                                          '(no world)')
        if picked:
            persona['world_id'] = world_id
            changed = True
        widgets.hint(tr('The world carries the lore every character in it shares.'))
        changed |= widgets.checkbox(persona, 'enabled', 'Play this sheet in character')
        changed |= widgets.multiline(persona, 'notes', 'Private notes (never sent to the model)', 44)
    return changed


def _appearance(app, persona):
    widgets.section('Reference photographs')
    changed = bool(reference_photographs(app, persona))
    picture_viewer(app, height=300.0)
    widgets.section('Written appearance')
    branch = persona['appearance']
    with widgets.properties('##appearance'):
        changed |= widgets.multiline(branch, 'summary', 'At a glance', 44)
        for key, caption in (('build', 'Build and height'), ('face', 'Face'), ('hair', 'Hair'),
                             ('eyes', 'Eyes'), ('skin', 'Skin'), ('age_reading', 'Apparent age')):
            changed |= widgets.text_field(branch, key, caption)
        for key, caption in (('outfit', 'Usual outfit'), ('marks', 'Scars, tattoos, marks'),
                             ('accessories', 'Accessories')):
            changed |= widgets.multiline(branch, key, caption, 40)
    widgets.section('For the image prompts')
    with widgets.properties('##appearance-prompts'):
        changed |= widgets.string_list(
            branch, 'visual_tags', 'Visual tags',
            'Short tags reused word for word in every image prompt. This is what keeps the '
            'character recognisable between two pictures.')
        changed |= widgets.string_list(branch, 'negative_tags', 'Never depict')
        changed |= widgets.multiline(branch, 'style_reference', 'Rendering style', 40)
    return changed


def _personality(persona):
    branch = persona['personality']
    with widgets.properties('##personality'):
        changed = widgets.multiline(branch, 'summary', 'In one sentence', 40)
        for key, caption in (('traits', 'Traits'), ('values', 'Values'), ('desires', 'Wants'),
                             ('fears', 'Fears'), ('flaws', 'Flaws'),
                             ('quirks', 'Quirks and habits')):
            changed |= widgets.string_list(branch, key, caption)
        for key, caption in (('humour', 'Sense of humour'), ('temperament', 'Temperament'),
                             ('moral_compass', 'Moral compass')):
            changed |= widgets.multiline(branch, key, caption, 40)
    return changed


def _speech(persona):
    branch = persona['speech']
    with widgets.properties('##speech'):
        changed = widgets.multiline(branch, 'style', 'Speaking style', 44)
        for key, caption in (('register', 'Register'), ('accent', 'Accent')):
            changed |= widgets.text_field(branch, key, caption)
        changed |= widgets.multiline(branch, 'vocabulary', 'Vocabulary and imagery', 40)
        for key, caption in (('verbal_tics', 'Verbal tics'), ('catchphrases', 'Catchphrases'),
                             ('languages', 'Languages spoken')):
            changed |= widgets.string_list(branch, key, caption)
        changed |= widgets.multiline(branch, 'narration_style', 'Narration style', 40)
    widgets.section('Example dialogues')
    widgets.hint(tr('A few exchanges written as the character speaks: the model imitates their '
                    'rhythm more than any description.'))
    changed |= widgets.multiline(branch, 'example_dialogues', 'Example dialogues', 140)
    return changed


def _background(persona):
    branch = persona['background']
    with widgets.properties('##background'):
        changed = widgets.text_field(branch, 'occupation', 'Occupation or role')
        changed |= widgets.multiline(branch, 'origin', 'Origin', 44)
        changed |= widgets.multiline(branch, 'story', 'Life story', 120)
        changed |= widgets.string_list(branch, 'skills', 'Skills')
        changed |= widgets.string_list(branch, 'possessions', 'Notable possessions')
        changed |= widgets.string_list(branch, 'factions', 'Factions and affiliations')
        changed |= widgets.multiline(branch, 'secrets', 'Secrets', 60)
        widgets.hint(tr('Secrets are given to the model as known but unspoken. They are not '
                        'sent to the scene describer.'))
    return changed


def _state_and_memory(app, persona):
    branch = persona['state']
    widgets.section('Right now — this is what evolves')
    with widgets.properties('##state'):
        changed = widgets.multiline(branch, 'scenario', 'Scene in progress', 60)
        for key, caption in (('location', 'Location'), ('time', 'Time in fiction'),
                             ('mood', 'Mood'), ('energy', 'Physical condition'),
                             ('outfit_now', 'Currently wearing')):
            changed |= widgets.text_field(branch, key, caption)
        changed |= widgets.string_list(branch, 'goals', 'Immediate goals')
        changed |= widgets.string_list(branch, 'tensions', 'Open tensions')
        if branch.get('updated'):
            widgets.hint(tr('Last change: ') + branch['updated'])

    memory = persona['memory']
    widgets.section('Memory')
    widgets.hint(tr('Memory stays explicit: nothing is taken from a conversation unless you put '
                    'it here.'))
    with widgets.properties('##memory'):
        changed |= widgets.string_list(memory, 'facts', 'Persistent facts')
    changed |= widgets.dictionary_list(memory, 'episodes', tr('Remembered episodes'),
                                       [('when', tr('When'), False),
                                        ('summary', tr('What happened'), True)], 140)
    return changed


def _relations(app, persona):
    widgets.hint(tr('How this character feels about the others, injected into every reply.'))
    others = [entry for entry in app.personas if entry['id'] != persona.get('id')]
    changed = False
    removed = -1
    relations = list(persona.get('relationships') or [])
    if not relations:
        cyui.space(8.0)
        cyui.text_faint(tr('No relationship yet.'))
    for index, relation in enumerate(relations):
        imgui.push_id('relation-%d' % index)
        cyui.space(4.0)
        cyui.begin_card('relation', '')
        title = relation.get('name') or relation.get('persona_id') or tr('(untitled)')
        raw().align_text_to_frame_padding()
        cyui.heading(title, 3)
        if relation.get('type'):
            imgui.same_line()
            cyui.badge(relation['type'])
        imgui.same_line()
        cyui.align_right(imgui.get_frame_height() * 2 + cyui.dp(8.0))
        if widgets.icon_button(cyui.icon.sync, 'Write the mirror bond on their sheet'):
            try:
                app.call('set_relation', {'persona_id': persona['id'], 'relation': relation,
                                          'mirror': True})
                app.notice = 'Mirror bond written.'
                app.load_persona()
            except CyToolError as exc:
                app.error = str(exc)
        imgui.same_line()
        if widgets.icon_button(cyui.icon.trash, 'Remove this bond'):
            removed = index
        with widgets.properties('##relation-fields'):
            target, picked = widgets.picker('Other character', relation.get('persona_id', ''),
                                            others, '(not in the library)')
            if picked:
                relation['persona_id'] = target
                match = next((o for o in others if o['id'] == target), None)
                if match:
                    relation['name'] = match.get('name', target)
                changed = True
            changed |= widgets.text_field(relation, 'name', 'Name as known')
            changed |= widgets.text_field(relation, 'type', 'Kind of bond')
            changed |= widgets.text_field(relation, 'label', 'Calls them')
            changed |= widgets.slider_float(relation, 'sentiment', 'Feeling', -1.0, 1.0)
            changed |= widgets.slider_float(relation, 'trust', 'Trust', 0.0, 1.0)
            changed |= widgets.checkbox(relation, 'known', 'They have met')
            changed |= widgets.multiline(relation, 'history', 'Shared history', 40)
            changed |= widgets.multiline(relation, 'tension', 'Current tension', 40)
            changed |= widgets.multiline(relation, 'secret', 'Kept from them', 40)
        cyui.end_card()
        imgui.pop_id()
    if removed >= 0:
        persona['relationships'].pop(removed)
        changed = True
    cyui.space(4.0)
    if cyui.icon_text_button(cyui.icon.add, tr('Add a relationship'), 'outline'):
        persona.setdefault('relationships', []).append(
            {'persona_id': '', 'name': '', 'type': '', 'sentiment': 0.0, 'trust': 0.5})
        changed = True
    return changed


def _media(app, persona):
    branch = persona['media']
    with widgets.properties('##media'):
        changed = widgets.checkbox(branch, 'enabled', 'Describe the shot with every reply')
        widgets.hint(tr('The description is returned as structured JSON for an image or video '
                        'tool. This Tool describes; it does not render.'))
        changed |= widgets.combo(branch, 'mode', 'How it is produced', ['director', 'inline'],
                                 ['Second constrained pass (reliable)',
                                  'Same reply (one generation)'])
        changed |= widgets.combo(branch, 'detail', 'Detail', ['minimal', 'standard', 'full'])
        installed = [entry for entry in app.models if entry.get('installed')]
        identifiers = [''] + [entry['id'] for entry in installed]
        captions = [tr('(same model as the conversation)')] + [entry['name'] for entry in installed]
        current = branch.get('director_model', '')
        index = identifiers.index(current) if current in identifiers else 0
        picked, index = widgets.choice('Model used for the description', index, captions)
        if picked:
            branch['director_model'] = identifiers[index]
            changed = True
        widgets.hint(tr('A larger model usually writes better shot descriptions than a small '
                        'roleplay model.'))
    widgets.section('Shot')
    with widgets.properties('##media-shot'):
        changed |= widgets.text_field(branch, 'default_shot', 'Default framing')
        changed |= widgets.multiline(branch, 'motion_style', 'Movement style', 40)
        changed |= widgets.multiline(branch, 'camera_notes', 'Camera notes', 40)
        changed |= widgets.slider_float(branch, 'duration_seconds', 'Clip length (s)', 1.0, 60.0)
        changed |= widgets.text_field(branch, 'aspect_ratio', 'Aspect ratio')
        changed |= widgets.string_list(branch, 'extra_targets', 'Extra rendering targets',
                                       'Names of forms a downstream tool expects. The describer '
                                       'fills one entry per name under "renderings".')
    return changed


def _voice(app, persona):
    branch = persona['voice']
    voices = [{'id': v['id'], 'name': '%s (%.0fs)' % (v['name'], v['seconds'])}
              for v in getattr(app, 'voices', [])]
    changed = False
    widgets.section('Voice')
    with widgets.properties('##voice'):
        chosen, picked = widgets.picker('Stable voice', branch.get('voice_id', ''), voices,
                                        '(no stable voice — a preset or a description is used)')
        if picked:
            branch['voice_id'] = chosen
            changed = True
        widgets.hint(tr('A stable voice is cloned from one recording, so every line of this '
                        'character sounds the same. Create one in the Voice tab.'))
        if branch.get('voice_id'):
            # Qwen3-TTS clones take no written instruction at all; saying so here avoids a
            # direction field that seems to do something and does nothing.
            widgets.hint(tr('A cloned voice reproduces its take: the standing direction and the '
                            '[tone:] marks only steer invented and preset voices. Pauses apply '
                            'to every voice.'))
        changed |= widgets.combo(branch, 'language', 'Spoken language',
                                 ['Auto', 'French', 'English', 'Spanish', 'German', 'Italian',
                                  'Portuguese', 'Russian', 'Chinese', 'Japanese', 'Korean'])
        changed |= widgets.combo(branch, 'delivery', 'Playback', ['paragraphs', 'complete'],
                                 ['Paragraph by paragraph', 'Whole take at once'])
        changed |= widgets.multiline(branch, 'instruction', 'Standing voice direction', 50)
    widgets.section('What is spoken')
    with widgets.properties('##voice-spoken'):
        changed |= widgets.checkbox(branch, 'enabled', 'Speak the replies')
        changed |= widgets.checkbox(branch, 'annotations',
                                    'Let the character write [tone:] and [pause:] marks')
        changed |= widgets.checkbox(branch, 'speak_narration', 'Also speak *stage directions*')
        widgets.hint(tr('The scene description is never spoken, whatever these say.'))
        changed |= widgets.checkbox(branch, 'use_persona_style',
                                    'Derive the delivery from the sheet and the scene')
    widgets.section('Speed and pitch')
    with widgets.properties('##voice-speed'):
        changed |= widgets.slider_float(branch, 'speed', 'Speed', 0.5, 2.0, '%.2fx')
        changed |= widgets.slider_float(branch, 'pitch', 'Pitch (semitones)', -12.0, 12.0, '%+.1f')
        widgets.hint(tr('Applied to every spoken line after the model, in scenes, batches and '
                        'translations; never to the take a stable voice is captured from. A few '
                        'semitones change the height of the voice, an octave turns it into '
                        'another voice.'))
    if widgets.small_button(tr('Natural speed and pitch') + '##voice-neutral', 'quiet'):
        branch['speed'], branch['pitch'] = 1.0, 0.0
        changed = True
    if not branch.get('voice_id'):
        widgets.section('Without a stable voice')
        with widgets.properties('##voice-invented'):
            changed |= widgets.multiline(branch, 'description', 'Voice to invent', 50)
            widgets.hint(tr('Filled in, this describes a voice for VoiceDesign. Empty, the '
                            'preset speaker below is used.'))
            changed |= widgets.combo(branch, 'speaker', 'Preset speaker', PRESET_SPEAKERS)
    changed |= _voice_languages(app, persona)
    return changed


LANGUAGE_SOURCES = ['same', 'voice', 'design', 'preset']
LANGUAGE_SOURCE_CAPTIONS = ['The same voice', 'Another stable voice', 'An invented voice',
                            'A preset speaker']


def _voice_languages(app, persona):
    """One entry per language the character should sound different in."""
    branch = persona['voice']
    widgets.section('Other languages')
    widgets.hint(tr('How this character sounds when a translated line is spoken. Keep the same '
                    'voice — with its accent, or with only its timbre — or give the language a '
                    'voice of its own. A language with no entry keeps the same voice and its '
                    'accent.'))
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
        cyui.space(4.0)
        cyui.begin_card('language', '')
        raw().align_text_to_frame_padding()
        cyui.heading(tr(entry.get('language', 'English')), 3)
        imgui.same_line()
        cyui.align_right(imgui.get_frame_height())
        if widgets.icon_button(cyui.icon.trash, 'Remove this language'):
            removed = index
        if entry.get('language') == own:
            cyui.callout('warning', tr("This is the character's own language: this entry is "
                                       'ignored. Change the main voice above instead.'))
        with widgets.properties('##language-fields'):
            edited |= widgets.combo(entry, 'language', 'Language', choices,
                                    [tr(language) for language in choices])
            edited |= widgets.combo(entry, 'source', 'Voice used', LANGUAGE_SOURCES,
                                    [tr(caption) for caption in LANGUAGE_SOURCE_CAPTIONS])
            source = entry.get('source', 'same')
            if source == 'same':
                edited |= widgets.combo(entry, 'accent', 'Accent', ['keep', 'native'],
                                        [tr("Keep the character's accent"),
                                         tr('Pronounce like a native speaker')])
                if branch.get('voice_id'):
                    widgets.hint(tr('Keep: the clone continues the take itself, accent '
                                    'included. Native: only the timbre is taken from the take; '
                                    'the words are pronounced as the model says them.'))
                else:
                    widgets.hint(tr('Without a stable voice, the accent is asked for in the '
                                    'voice direction.'))
            elif source == 'voice':
                chosen, picked = widgets.picker('Stable voice for this language',
                                                entry.get('voice_id', ''), voices,
                                                '(choose a voice)')
                if picked:
                    entry['voice_id'] = chosen
                    edited = True
                widgets.hint(tr('Capture one in the Voice tab with the take language set to %s '
                                'and keep it as the voice of that language.')
                             % tr(entry.get('language', 'English')))
            elif source == 'design':
                edited |= widgets.multiline(entry, 'description', 'Voice to invent', 44)
                widgets.hint(tr('For example: a man in his forties from London, low and dry, '
                                'slow delivery.'))
            else:
                edited |= widgets.combo(entry, 'speaker', 'Preset speaker', PRESET_SPEAKERS)
            if source in ('design', 'preset') or (source == 'same' and not branch.get('voice_id')):
                edited |= widgets.multiline(entry, 'instruction', 'Direction for this language', 40)
            edited |= widgets.integer(entry, 'seed', 'Seed (-1 keeps the main voice seed)', -1, -1)
        cyui.end_card()
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
        cyui.space(4.0)
        state = getattr(app, 'new_language', None)
        if state not in free:
            state = 'English' if 'English' in free else free[0]
        raw().set_next_item_width(cyui.dp(200.0))
        _, position = raw().combo('##new-language', free.index(state),
                                  [tr(language) for language in free])
        app.new_language = free[position]
        imgui.same_line()
        if cyui.icon_text_button(cyui.icon.add, tr('Add a language'), 'outline'):
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
    changed = False
    widgets.section('Model')
    with widgets.properties('##generation'):
        picked, index = widgets.choice('Conversation model', index, captions)
        if picked:
            branch['llm_model'] = identifiers[index]
            changed = True
        changed |= widgets.combo(branch, 'device', 'Device', ['cpu', 'cuda'], ['CPU', 'NVIDIA GPU'])
        changed |= widgets.text_field(branch, 'language', 'Reply language')
        changed |= widgets.checkbox(branch, 'stay_in_character', 'Stay in character')
        changed |= widgets.checkbox(branch, 'allow_narration', 'Allow narration')
    widgets.section('Instructions')
    with widgets.properties('##generation-prompt'):
        changed |= widgets.multiline(branch, 'system_prompt', 'System prompt', 70)
        changed |= widgets.multiline(branch, 'behaviour_rules', 'Behaviour rules', 50)
    widgets.section('Sampling')
    with widgets.properties('##generation-sampling'):
        changed |= widgets.slider_float(branch, 'temperature', 'Creativity', 0.0, 2.0)
        changed |= widgets.slider_float(branch, 'top_p', 'Top-p', 0.0, 1.0)
        changed |= widgets.slider_float(branch, 'repeat_penalty', 'Repetition penalty', 0.5, 2.0)
        changed |= widgets.slider_int(branch, 'response_length', 'Reply length (tokens)', 16, 4096)
        changed |= widgets.integer(branch, 'seed', 'Seed (-1 random)', -1, -1)
    widgets.section('Resources')
    with widgets.properties('##generation-resources'):
        changed |= widgets.slider_int(branch, 'threads', 'CPU threads', 1, 64)
        changed |= widgets.slider_int(branch, 'context_budget', 'Context budget (characters)',
                                     1024, 32768)
        widgets.hint(tr('The sheet, the world and the cast get 70 % of this budget; the rest is '
                        'kept for the conversation. Preview the prompt to see what was left out.'))
    return changed


def _character_toolbar(app):
    if cyui.begin_toolbar('##character-tools'):
        imgui.begin_disabled(app.busy)
        if cyui.icon_text_button(cyui.icon.add, tr('New character'), 'outline'):
            try:
                outputs = app.call('create_persona', {'name': tr('New character')})
                app.refresh_library()
                app.select_persona(outputs['id'])
            except CyToolError as exc:
                app.error = str(exc)
        if app.persona is not None:
            imgui.same_line()
            if widgets.icon_button(cyui.icon.copy, 'Duplicate this character') and app.persona_id:
                try:
                    outputs = app.call('duplicate_persona', {'persona_id': app.persona_id})
                    app.refresh_library()
                    app.select_persona(outputs['id'])
                except CyToolError as exc:
                    app.error = str(exc)
            cyui.toolbar_separator()
            raw().align_text_to_frame_padding()
            cyui.text_dim(tr('Revision'))
            imgui.same_line()
            raw().set_next_item_width(cyui.dp(90.0))
            _, app.restore_revision = raw().input_int('##restore-revision',
                                                      getattr(app, 'restore_revision', 1))
            imgui.same_line()
            if widgets.icon_button(cyui.icon.undo, 'Restore this revision (as a new revision)') \
                    and app.persona_id:
                try:
                    app.call('restore_persona', {'persona_id': app.persona_id,
                                                 'revision': max(0, app.restore_revision)})
                    app.load_persona()
                    app.notice = 'Revision restored as a new revision.'
                except CyToolError as exc:
                    app.error = str(exc)
            imgui.same_line()
            if widgets.icon_button(cyui.icon.clock, 'List the revisions') and app.persona_id:
                try:
                    app.notice = 'Revisions: ' + ', '.join(
                        str(r['revision']) for r in app.call(
                            'persona_revisions', {'persona_id': app.persona_id})['revisions'])
                except CyToolError as exc:
                    app.error = str(exc)
            save = tr('Save')
            imgui.same_line()
            cyui.align_right(cyui.button_width('  ' + save) + cyui.dp(28.0)
                             + imgui.get_frame_height() + cyui.dp(10.0))
            if widgets.icon_button(cyui.icon.trash, 'Move to trash (data/personas/.trash)') \
                    and app.persona_id:
                try:
                    app.call('remove_persona', {'persona_id': app.persona_id})
                    app.notice = 'Moved to data/personas/.trash — nothing was deleted.'
                    app.persona_id = ''
                    app.refresh_library()
                except CyToolError as exc:
                    app.error = str(exc)
            imgui.same_line()
            if cyui.icon_text_button(cyui.icon.save, save, 'primary' if app.dirty else 'secondary'):
                app.save_persona()
        imgui.end_disabled()
    cyui.end_toolbar()


SHEET_TABS = [('Identity', 'identity'), ('Appearance', 'appearance'),
              ('Personality', 'personality'), ('Speech', 'speech'), ('Background', 'background'),
              ('State & memory', 'state'), ('Relationships', 'relations'),
              ('Visual direction', 'media'), ('Voice', 'voice'), ('Model', 'model')]


def characters(app):
    _character_toolbar(app)
    if app.persona is None:
        widgets.empty('No character selected',
                      'Pick one in the bar at the top, or create a new character.',
                      cyui.icon.contact)
        return

    persona = app.persona
    drawers = {'identity': lambda: _identity(app, persona),
               'appearance': lambda: _appearance(app, persona),
               'personality': lambda: _personality(persona),
               'speech': lambda: _speech(persona),
               'background': lambda: _background(persona),
               'state': lambda: _state_and_memory(app, persona),
               'relations': lambda: _relations(app, persona),
               'media': lambda: _media(app, persona),
               'voice': lambda: _voice(app, persona),
               'model': lambda: _generation(app, persona)}
    cyui.space(6.0)
    caption = widgets.page_tabs('sheet', ['Identity', 'Appearance', 'Personality', 'Speech',
                                          'Background', 'State & memory', 'Relationships',
                                          'Visual direction', 'Voice', 'Model'], SHEET_TAB)
    # The sheet takes the rest of the page and scrolls on its own; the toolbar above stays
    # where it is.
    imgui.begin_child('sheet-body', (0, 0), 0)
    changed = bool(drawers[dict(SHEET_TABS)[caption]]())
    cyui.space(12.0)
    if SHEET_BOTTOM:
        raw().set_scroll_y(raw().get_scroll_max_y())
    imgui.end_child()
    if changed:
        app.dirty = True


# ------------------------------------------------------------------------ worlds

def _world_toolbar(app):
    if cyui.begin_toolbar('##world-tools'):
        raw().align_text_to_frame_padding()
        cyui.text_dim(tr('World'))
        imgui.same_line()
        identifiers = [''] + [entry['id'] for entry in app.worlds]
        captions = [tr('(none)')] + [entry.get('name', entry['id']) for entry in app.worlds]
        current = (app.world or {}).get('id', '')
        index = identifiers.index(current) if current in identifiers else 0
        raw().set_next_item_width(cyui.dp(300.0))
        imgui.begin_disabled(app.busy)
        picked, index = raw().combo('##world', index, captions)
        if picked:
            try:
                app.flush()
                chosen = identifiers[index]
                app.world = normalize_world(app.call('get_world', {'world_id': chosen})['world']) \
                    if chosen else None
            except CyToolError as exc:
                app.error = str(exc)
        imgui.same_line()
        if cyui.icon_text_button(cyui.icon.add, tr('New world'), 'outline'):
            try:
                outputs = app.call('create_world', {'name': tr('New world')})
                app.refresh_library_names()
                app.world = normalize_world(outputs['world'])
                app.notice = 'World created: ' + outputs['id']
            except CyToolError as exc:
                app.error = str(exc)
        if app.world is not None:
            save = tr('Save')
            imgui.same_line()
            cyui.align_right(cyui.button_width('  ' + save) + cyui.dp(28.0))
            if cyui.icon_text_button(cyui.icon.save, save,
                                     'primary' if app.world_dirty else 'secondary'):
                app.save_world()
        imgui.end_disabled()
    cyui.end_toolbar()


def worlds(app):
    _world_toolbar(app)
    if app.world is None:
        widgets.empty('No world selected',
                      'A world holds the lore shared by several characters: places, factions, '
                      'laws, timeline and what must stay true.', cyui.icon.globe)
        return

    world = app.world
    members = [entry['name'] for entry in app.personas if entry.get('world_id') == world.get('id')]
    cyui.space(4.0)
    raw().align_text_to_frame_padding()
    cyui.text_dim(tr('Cast: '))
    for name in members:
        imgui.same_line()
        cyui.badge(name)
    if not members:
        imgui.same_line()
        cyui.text_faint(tr('nobody yet'))
    cyui.space(2.0)

    imgui.begin_child('world-body', (0, 0), 0)
    changed = False
    if cyui.begin_section(tr('The world') + '###world-identity'):
        with widgets.properties('##world'):
            changed |= widgets.text_field(world, 'name', 'Name')
            changed |= widgets.multiline(world, 'summary', 'Pitch', 44)
            changed |= widgets.text_field(world, 'genre', 'Genre')
            changed |= widgets.text_field(world, 'tone', 'Tone')
            changed |= widgets.text_field(world, 'era', 'Era')
            changed |= widgets.text_field(world, 'language', 'Default language')
            changed |= widgets.multiline(world, 'setting', 'Setting', 110)
        cyui.end_section()
    if cyui.begin_section(tr('Places, factions and laws') + '###world-lore'):
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
        cyui.end_section()
    if cyui.begin_section(tr('Timeline and glossary') + '###world-history', False):
        changed |= widgets.dictionary_list(world, 'history', tr('Timeline'),
                                           [('when', tr('When'), False),
                                            ('what', tr('What happened'), True)])
        changed |= widgets.dictionary_list(world, 'glossary', tr('Glossary'),
                                           [('term', tr('Term'), False),
                                            ('meaning', tr('Meaning'), True)])
        cyui.end_section()
    if cyui.begin_section(tr('What the story keeps to') + '###world-canon'):
        with widgets.properties('##world-canon'):
            changed |= widgets.multiline(world, 'canon', 'Canon — what must stay true', 70)
            changed |= widgets.multiline(world, 'forbidden',
                                         'Out of bounds — what never happens here', 50)
            changed |= widgets.multiline(world, 'narration_style', 'House narration style', 40)
            changed |= widgets.multiline(world, 'visual_style', 'House visual style', 40)
            widgets.hint(tr('The visual style is merged into every image and video description '
                            'of the characters in this world.'))
        cyui.end_section()
    _term_translations(app, world)
    if changed:
        app.world_dirty = True
    imgui.end_child()


def _term_translations(app, world):
    """How the places, factions and terms of this world are rendered in each language.

    Filled by the translator the first time a term appears; what you write here is kept and
    never replaced. Saved on its own, through set_term_translations.
    """
    smoke = '--smoke-open' in sys.argv            # screenshots of this section, in tests
    if smoke:
        raw().set_next_item_open(True)
    if not cyui.begin_section(tr('Translated terms') + '###world-terms', False):
        return
    if smoke:
        raw().set_scroll_here_y(0.0)
    widgets.hint(tr('Every translation renders these the same way. The translator fills in a '
                    'term the first time a scene mentions it; correct it here and your rendering '
                    'is kept for good. Leave a rendering empty to let the translator render it '
                    'again.'))
    state = app.__dict__.setdefault('term_editor', {'language': 'English', 'drafts': {}})
    choices = list(LANGUAGES)
    index = choices.index(state['language']) if state['language'] in choices else 0
    with widgets.properties('##terms-language'):
        changed, index = widgets.choice('Language##terms', index, [tr(l) for l in choices])
    if changed:
        state['language'], state['drafts'] = choices[index], {}
    language = state['language']
    table = (world.get('term_translations') or {}).get(language) or {}
    terms = translation_module.world_terms(world)
    if not terms:
        cyui.text_faint(tr('This world has no place, faction or glossary term yet.'))
        cyui.end_section()
        return
    flags = (raw().TableFlags_.row_bg | raw().TableFlags_.borders_inner_h
             | raw().TableFlags_.sizing_stretch_prop)
    if raw().begin_table('##terms', 3, flags):
        raw().table_setup_column(tr('Term'), raw().TableColumnFlags_.width_stretch, 0.35)
        raw().table_setup_column(tr('Rendering'), raw().TableColumnFlags_.width_stretch, 0.45)
        raw().table_setup_column(tr('Source'), raw().TableColumnFlags_.width_stretch, 0.20)
        raw().table_headers_row()
        for item in terms:
            imgui.push_id('term-' + item['term'])
            entry = table.get(item['term']) or {}
            raw().table_next_row()
            raw().table_set_column_index(0)
            raw().align_text_to_frame_padding()
            raw().text_unformatted(item['term'])
            imgui.same_line()
            cyui.text_faint(tr(item['kind']))
            raw().table_set_column_index(1)
            value = state['drafts'].get(item['term'], entry.get('text', ''))
            raw().set_next_item_width(-1.17549435e-38)
            edited, value = raw().input_text('##rendering', value)
            if edited:
                state['drafts'][item['term']] = value
            raw().table_set_column_index(2)
            raw().align_text_to_frame_padding()
            if item['term'] in state['drafts']:
                cyui.badge(tr('modified'), 'warning')
            elif entry.get('source') == 'person':
                cyui.badge(tr('yours'), 'success')
            elif entry.get('text'):
                cyui.text_faint(tr('by %s') % (entry.get('model') or tr('the model')))
            else:
                cyui.text_faint(tr('not rendered yet'))
            imgui.pop_id()
        raw().end_table()
    cyui.space(4.0)
    imgui.begin_disabled(app.busy or not state['drafts'])
    if cyui.icon_text_button(cyui.icon.save, tr('Save the terms'), 'outline'):
        _save_terms(app, world, language, [{'term': term, 'text': text}
                                           for term, text in state['drafts'].items()])
        state['drafts'] = {}
    imgui.end_disabled()
    imgui.same_line()
    models_rendered = [term for term, entry in table.items() if entry.get('source') == 'model']
    imgui.begin_disabled(app.busy or not models_rendered)
    if widgets.button('Forget what the translator rendered', 'quiet'):
        _save_terms(app, world, language, [{'term': term, 'text': ''} for term in models_rendered])
        state['drafts'] = {}
    imgui.end_disabled()
    cyui.end_section()


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
    modes = {'Discussion': discussion, 'Proposal': _proposal}
    modes[widgets.page_tabs('assistant-modes', ['Discussion', 'Proposal'], SHEET_TAB)](app)


def _proposal(app):
    widgets.hint(tr('Ask for a sheet, a world, or one section of either. The assistant does not '
                    'play the character and writes nothing until you apply it.'))
    targets = ['sheet', 'identity', 'appearance', 'personality', 'speech', 'background', 'state',
               'memory', 'media', 'dialogues', 'notes']
    world_targets = ['world', 'setting', 'locations', 'factions', 'rules', 'history', 'glossary',
                     'canon']
    kinds = ['persona', 'world']
    imgui.begin_child('proposal-page', (0, 0), 0)
    widgets.section('What to write')
    with widgets.properties('##proposal-what'):
        index = kinds.index(app.proposal_kind) if app.proposal_kind in kinds else 0
        widgets.row('Write for')
        changed, index = cyui.segmented('##write-for', [tr('A character'), tr('A world')], index, -1)
        if changed:
            app.proposal_kind = kinds[index]
            app.proposal_target = 'sheet' if app.proposal_kind == 'persona' else 'world'
        choices = targets if app.proposal_kind == 'persona' else world_targets
        position = choices.index(app.proposal_target) if app.proposal_target in choices else 0
        changed, position = widgets.choice(
            'Section', position, [tr(TARGET_CAPTIONS.get(choice, choice)) for choice in choices])
        if changed:
            app.proposal_target = choices[position]

        threads = [{'id': t['id'], 'name': '%s (%d)' % (t['title'] or 'Discussion', t['turns'])}
                   for t in app.threads if t['turns']]
        chosen, picked = widgets.picker('Build on a discussion',
                                        getattr(app, 'author_thread', ''), threads, '(none)')
        if picked:
            app.author_thread = chosen
        if threads:
            widgets.hint(tr('What was said in that discussion is handed to the assistant along '
                            'with your request.'))

        guide = getattr(app, 'author_image', None)
        if guide is None:
            guide = app.author_image = {'image': ''}
        widgets.text_field(guide, 'image', 'Reference picture (full path, or a file in data/inputs)')
        widgets.hint(tr('It is read by the vision model first, and what it shows is handed to '
                        'the assistant as the appearance to work from.'))

    # The assistant has no sheet of its own, so its model and device are chosen here.
    settings = getattr(app, 'author_settings', None)
    if settings is None:
        settings = app.author_settings = {'llm_model': '', 'device': '', 'response_length': 2048}
    installed = [entry for entry in app.models if entry.get('installed')]
    if cyui.begin_section(tr('Writing model') + '###author-model', False):
        with widgets.properties('##proposal-model'):
            identifiers = [''] + [entry['id'] for entry in installed]
            captions = [tr('(the model of the selected character)')] + [e['name'] for e in installed]
            current = settings['llm_model']
            index = identifiers.index(current) if current in identifiers else 0
            picked, index = widgets.choice('Model used to write', index, captions)
            if picked:
                settings['llm_model'] = identifiers[index]
            widgets.hint(tr('Writing a sheet is a structured task. A larger, more '
                            'instruction-following model does it better than a small roleplay '
                            'one, which is what plays the character.'))
            widgets.combo(settings, 'device', 'Device', ['', 'cuda', 'cpu'],
                          [tr('(the device of the character)'), tr('NVIDIA GPU'), tr('CPU')])
            widgets.slider_int(settings, 'response_length', 'Maximum proposal length (tokens)',
                               256, 4096)
        cyui.end_section()
    if not installed:
        cyui.callout('warning', tr('No model is installed yet; install one in Models.'))

    widgets.section('What do you want?')
    _, app.author_request = raw().input_text_multiline('##request', app.author_request,
                                                       (-1, cyui.dp(84.0)))
    imgui.begin_disabled(app.busy or not app.author_request.strip())
    if cyui.icon_text_button(cyui.icon.send, tr('Ask'), 'primary'):
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
        cyui.spinner('##author-writing', 7.0)
        imgui.same_line()
        cyui.text_faint(tr('Writing...'))

    if app.proposal is not None:
        cyui.space(6.0)
        cyui.begin_card('proposal-card', tr('Proposal'), 0.0, 'accent')
        body = app.proposal if isinstance(app.proposal, str) \
            else json.dumps(app.proposal, ensure_ascii=False, indent=2)
        with cyui.scoped_font(cyui.mono_font()):
            edited, body = raw().input_text_multiline('##proposal-body', body,
                                                      (-1, cyui.dp(280.0)))
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
        if cyui.icon_text_button(cyui.icon.check,
                                 tr('Apply to the selected character' if app.proposal_kind == 'persona'
                                    else 'Apply to the selected world'), 'outline'):
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
        if widgets.button('Discard', 'danger'):
            app.proposal = None
        imgui.end_disabled()
        cyui.end_card()
    imgui.end_child()


# ------------------------------------------------------------------------ library

def library_tab(app):
    modes = {'Examples': _examples, 'Pictures': library_gallery, 'Export and import': _exchange,
             'ComfyUI': comfyui_tab}
    modes[widgets.page_tabs('library-modes', ['Examples', 'Pictures', 'Export and import',
                                              'ComfyUI'], SHEET_TAB)](app)


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
    widgets.hint(tr('Worlds ready to play, each with its cast. Importing one copies it into your '
                    'library: the example itself never changes, and a character you already '
                    'have is never overwritten.'))
    if widgets.icon_button(cyui.icon.folder, 'Open the examples folder'):
        open_path(getattr(app, 'examples_folder', ''))
    imgui.same_line()
    if widgets.icon_button(cyui.icon.refresh, 'Refresh the list'):
        app.examples = None
        return
    if not app.examples:
        widgets.empty('No example found', 'The examples live in app/examples.', cyui.icon.library)
        return
    imgui.begin_child('examples', (0, 0), 0)
    for item in app.examples:
        imgui.push_id('example-' + item['id'])
        cyui.begin_card('example', '')
        raw().align_text_to_frame_padding()
        cyui.heading(item['world'], 3)
        if item.get('genre'):
            imgui.same_line()
            cyui.badge(item['genre'])
        if item.get('imported'):
            imgui.same_line()
            cyui.badge(tr('in your library'), 'success')
        raw().push_text_wrap_pos(0.0)
        raw().text_unformatted(item.get('summary', ''))
        raw().pop_text_wrap_pos()
        cyui.space(2.0)
        with widgets.properties('##example-facts', 140.0):
            widgets.row('Characters')
            raw().text_wrapped(', '.join(entry['name'] for entry in item['characters']))
            if item.get('voices'):
                widgets.row('Stable voices')
                raw().text_wrapped(tr('%d stable voices included — they come in with the import.')
                                   % item['voices'])
            if item.get('scenes'):
                widgets.row('Scenes')
                raw().text_wrapped(', '.join('%s (%d)' % (scene['title'], scene['lines'])
                                             for scene in item['scenes']))
        if item.get('imported'):
            widgets.hint(tr('Already in your library — importing it again makes copies.'))
        imgui.begin_disabled(app.busy)
        if cyui.icon_text_button(cyui.icon.download,
                                 tr('Import again') if item.get('imported')
                                 else tr('Import this world'),
                                 'secondary' if item.get('imported') else 'outline'):
            app.submit('import_personas', {'file': item['file'], 'rename': True}, 'import')
        imgui.end_disabled()
        cyui.end_card()
        cyui.space(4.0)
        imgui.pop_id()
    imgui.end_child()


def _exchange(app):
    imgui.begin_child('exchange', (0, 0), 0)
    widgets.section('Export')
    widgets.hint(tr('An export is self-contained: the sheets, their world and their voice '
                    'descriptors, so a character can be carried to another machine.'))
    selection = getattr(app, 'export_selection', None)
    if selection is None:
        selection = app.export_selection = {}
    with widgets.properties('##export'):
        widgets.row('Characters')
        for entry in app.personas:
            checked = selection.get(entry['id'], entry['id'] == app.persona_id)
            _, checked = raw().checkbox(entry['name'] + '##export-' + entry['id'], checked)
            selection[entry['id']] = checked
        options = {'audio': getattr(app, 'export_audio', False),
                   'scenes': getattr(app, 'export_scenes', False)}
        widgets.checkbox(options, 'audio', 'Include the reference recordings (produces a .zip)')
        widgets.checkbox(options, 'scenes', 'Include their scenes (the words, not the takes)')
        app.export_audio, app.export_scenes = options['audio'], options['scenes']
    imgui.begin_disabled(app.busy)
    if cyui.icon_text_button(cyui.icon.export_file, tr('Export the selection'), 'primary'):
        chosen = [identifier for identifier, on in selection.items() if on]
        if chosen:
            app.submit('export_personas', {'persona_ids': chosen,
                                           'include_audio': app.export_audio,
                                           'include_sessions': app.export_scenes}, 'export')
        else:
            app.error = 'Select at least one character.'
    imgui.same_line()
    if widgets.icon_button(cyui.icon.folder, 'Open the exports folder'):
        open_path(EXPORTS)
    imgui.end_disabled()

    widgets.section('Import')
    widgets.hint(tr('Drop a bundle in data/inputs, or give its full path. An existing character '
                    'is never overwritten: a clash creates a new identifier.'))
    with widgets.properties('##import'):
        widgets.row('Bundle file')
        _, app.import_path = raw().input_text('##bundle-file', getattr(app, 'import_path', ''))
    imgui.begin_disabled(app.busy or not app.import_path.strip())
    if cyui.icon_text_button(cyui.icon.import_file, tr('Import'), 'outline'):
        app.submit('import_personas', {'file': app.import_path, 'rename': True}, 'import')
    imgui.end_disabled()
    imgui.same_line()
    if widgets.icon_button(cyui.icon.folder, 'Open data/inputs'):
        open_path(DATA / 'inputs')

    widgets.section('Scenes')
    sessions = getattr(app, 'sessions', [])
    if not sessions:
        cyui.text_faint(tr('No scene yet.'))
    flags = raw().TableFlags_.row_bg | raw().TableFlags_.borders_inner_h
    if sessions and raw().begin_table('##scenes', 3, flags):
        raw().table_setup_column(tr('Scene'), raw().TableColumnFlags_.width_stretch)
        raw().table_setup_column(tr('Lines'), raw().TableColumnFlags_.width_fixed, cyui.dp(70.0))
        raw().table_setup_column(tr('Modified'), raw().TableColumnFlags_.width_fixed,
                                 cyui.dp(170.0))
        raw().table_headers_row()
        for entry in sessions:
            raw().table_next_row()
            raw().table_set_column_index(0)
            raw().text_unformatted(entry.get('title', entry['id']))
            raw().table_set_column_index(1)
            cyui.text_dim(str(entry.get('turns', 0)))
            raw().table_set_column_index(2)
            cyui.text_faint(str(entry.get('modified', '')))
        raw().end_table()
    imgui.end_child()


# ------------------------------------------------------------------------- models

def _model_card(app, entry, accepted):
    imgui.push_id(entry['id'])
    cyui.begin_card('model', '')
    raw().align_text_to_frame_padding()
    cyui.heading(entry['name'], 3)
    imgui.same_line()
    if entry['installed']:
        cyui.badge(tr('installed'), 'success')
    elif entry.get('presentBytes'):
        cyui.badge(tr('partly downloaded'), 'warning')
    else:
        cyui.badge(tr('not installed'))
    cyui.text_faint('%.2f GB · %s · RAM %d GB · VRAM %d GB'
                    % (entry['sizeBytes'] / 1e9, entry['id'], entry.get('ramGiB', 0),
                       entry.get('vramGiB', 0)))
    if entry.get('notes'):
        raw().push_text_wrap_pos(0.0)
        raw().text_unformatted(entry['notes'])
        raw().pop_text_wrap_pos()
    cyui.space(2.0)
    raw().align_text_to_frame_padding()
    cyui.text_dim(tr('Licence: ') + (entry.get('license') or tr('not declared')))
    if entry.get('source'):
        imgui.same_line()
        if widgets.icon_button(cyui.icon.link, 'Official page and licence'):
            webbrowser.open(entry['source'])
    already = entry.get('licenseAccepted', False)
    checked = accepted.get(entry['id'], already)
    _, checked = cyui.toggle_switch(tr('I personally accept this licence'), checked)
    accepted[entry['id']] = checked
    imgui.begin_disabled(app.busy or not checked)
    if cyui.icon_text_button(cyui.icon.download if not entry['installed'] else cyui.icon.repair,
                             tr('Download / resume' if not entry['installed']
                                else 'Repair / verify'),
                             'outline' if not entry['installed'] else 'secondary'):
        app.submit('install_llm', {'model': entry['id'], 'accept_license': True}, 'install_llm')
    imgui.end_disabled()
    cyui.end_card()
    cyui.space(4.0)
    imgui.pop_id()


def models_tab(app):
    if cyui.begin_toolbar('##models-tools'):
        imgui.begin_disabled(app.busy)
        if widgets.icon_button(cyui.icon.refresh, 'Refresh'):
            app.submit('list_models', {'verify': False}, 'list_models')
        imgui.same_line()
        if cyui.icon_text_button(cyui.icon.check, tr('Verify the installed weights'), 'ghost'):
            app.submit('list_models', {'verify': True}, 'list_models')
        imgui.same_line()
        if cyui.icon_text_button(cyui.icon.power, tr('Unload the resident model'), 'ghost'):
            app.submit('unload_model', {}, 'unload_model')
        free = (app.diagnosis.get('paths') or {}).get('freeBytes')
        if free:
            text = tr('Free space: %.1f GB') % (free / 1e9)
            imgui.same_line()
            cyui.align_right(raw().calc_text_size(text).x + cyui.dp(6.0))
            raw().align_text_to_frame_padding()
            cyui.text_faint(text)
        imgui.end_disabled()
    cyui.end_toolbar()

    imgui.begin_child('models-page', (0, 0), 0)
    engine = app.engine or {}
    widgets.section('Engine')
    with widgets.properties('##engine'):
        for key, caption in (('cpu', 'llama.cpp CPU'), ('cuda', 'NVIDIA CUDA')):
            info = engine.get(key) or {}
            widgets.row(caption)
            installed = info.get('installed')
            raw().align_text_to_frame_padding()
            cyui.status_dot(cyui.palette().success if installed else cyui.palette().textFaint)
            imgui.same_line()
            raw().text_unformatted(tr('installed') if installed else tr('absent'))
            if info.get('devices'):
                lines = info['devices'].strip().splitlines()
                widgets.hint(lines[1] if len(lines) > 1 else info['devices'])
    imgui.begin_disabled(app.busy)
    if cyui.icon_text_button(cyui.icon.repair, tr('Install / repair the CUDA engine'), 'outline'):
        app.submit('install_cuda', {}, 'install_cuda')
    imgui.same_line()
    if cyui.icon_text_button(cyui.icon.download, tr('Install / update the CPU engine'),
                             'secondary'):
        app.submit('update', {'kind': 'engine', 'action': 'download'}, 'update')
    imgui.end_disabled()

    widgets.section('Conversation models')
    widgets.hint(tr('Weights live in data/models/llm. A download can be cancelled and resumed; '
                    'nothing is marked installed before its SHA-256 matches.'))
    cyui.space(2.0)
    accepted = getattr(app, 'license_accept', None)
    if accepted is None:
        accepted = app.license_accept = {}
    if not app.models:
        cyui.text_faint(tr('The model list has not been read yet.'))
    for entry in app.models:
        _model_card(app, entry, accepted)
    imgui.end_child()


# ------------------------------------------------------------------------ updates

UPDATE_ACTIONS = [('check', 'Check', 'refresh'), ('download', 'Download', 'download'),
                  ('activate', 'Activate', 'check'), ('rollback', 'Roll back', 'undo')]


def updates_tab(app):
    imgui.begin_child('updates-page', (0, 0), 0)
    widgets.hint(tr('The application, the engine and the weights are three separate streams. '
                    'Weights follow the Models tab. data/ is never replaced.'))
    widgets.section('Preferences')
    with widgets.properties('##updates'):
        widgets.row('GitHub repository of this Tool (owner/name)')
        _, app.updates['repository'] = raw().input_text('##repository',
                                                        app.updates.get('repository', ''))
        if not app.updates.get('repository'):
            widgets.hint(tr('No repository is configured for this Tool, so the application '
                            'stream cannot be checked. The engine stream works without one.'))
        widgets.checkbox(app.updates, 'auto_check', 'Check at startup')
        widgets.checkbox(app.updates, 'auto_download', 'Download updates at startup')
    if cyui.icon_text_button(cyui.icon.save, tr('Save these preferences'), 'outline'):
        app.persist()
        app.notice = 'Preferences saved.'

    imgui.begin_disabled(app.busy)
    for kind, caption in (('engine', 'llama.cpp engine'), ('app', 'CyTools application')):
        widgets.section(caption)
        for position, (action, label, glyph) in enumerate(UPDATE_ACTIONS):
            if position:
                imgui.same_line()
            variant = 'danger' if action == 'rollback' else 'secondary'
            if cyui.icon_text_button(getattr(cyui.icon, glyph), tr(label) + '##' + kind + action,
                                     variant):
                app.submit('update', {'kind': kind, 'action': action,
                                      'repository': app.updates.get('repository', '')}, 'update')
    imgui.end_disabled()
    cyui.space(8.0)
    cyui.callout('info', tr('A staged application is activated at the next launch, under a lock, '
                            'and the previous version is kept for a roll back. An update is '
                            'verified before activation; a published checksum is not a '
                            'signature.'))
    imgui.end_child()


# --------------------------------------------------------------------- diagnostics

def diagnostics(app):
    if cyui.begin_toolbar('##diagnostics-tools'):
        imgui.begin_disabled(app.busy)
        if cyui.icon_text_button(cyui.icon.repair, tr('Run a diagnosis'), 'primary'):
            app.submit('diagnose_backend', {'verify': False}, 'diagnose_backend')
        imgui.same_line()
        if cyui.icon_text_button(cyui.icon.check, tr('Deep check (SHA-256 of every model)'),
                                 'ghost'):
            app.submit('diagnose_backend', {'verify': True}, 'diagnose_backend')
        imgui.end_disabled()
        imgui.same_line()
        if widgets.icon_button(cyui.icon.folder, 'Open the reports folder'):
            open_path(DATA / 'reports')
        if app.diagnosis:
            imgui.same_line()
            if widgets.icon_button(cyui.icon.copy, 'Copy the diagnosis'):
                raw().set_clipboard_text(json.dumps(app.diagnosis, ensure_ascii=False, indent=2))
                app.notice = 'Diagnosis copied.'
    cyui.end_toolbar()
    if not app.diagnosis:
        widgets.empty('No diagnosis yet',
                      'Run a diagnosis to see models, engines, devices and paths.',
                      cyui.icon.repair)
        return
    widgets.hint(tr('The text below is selectable and copyable. See VALIDATION.md for what has '
                    'actually been executed on this machine.'))
    body = json.dumps(app.diagnosis, ensure_ascii=False, indent=2)
    with cyui.scoped_font(cyui.mono_font()):
        raw().input_text_multiline('##diagnosis-body', body, (-1, -1),
                                   raw().InputTextFlags_.read_only)
