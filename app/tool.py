"""CyTools_PersonaRP runtime: persistent characters, shared worlds, scenes and dialogue.

Every interface — CLI, JSONL, HTTP, MCP and the desktop window — goes through this one
Runtime. There is no second scheduler and no second job registry.
"""
from installation_ui import configure as configure_installation_storage

configure_installation_storage()

import copy
import json
import shutil
import sys
from pathlib import Path

from cytools_core import CyToolError, Runtime, load_manifest
from cytools_core.transports.cli import run_cli

from personarp import (assistant, authoring, batches, comfyui, examples, imaging, library,
                       maintenance, models, scene, sessions, translation)
from personarp.voice import catalog as voice_catalog, delivery as voice_delivery
from personarp.voice import runner as voice_runner, stable as voice_stable
from personarp.locks import exclusive
from personarp.paths import (APP, DATA, EXPORTS, LLM_MODELS, ROOT, RUNTIME, SETTINGS,
                             ensure_data_layout, read_json, write_json)
from personarp import prompting
from personarp.prompting import build_system_prompt, chatml, messages as build_messages
from personarp.resident import ResidentModel
from personarp.schemas import normalize_persona, normalize_scene, normalize_world

from model_options import Runtime, ProcessWorker          # noqa: F811 - adds model-library ops


def _first_installed():
    for model in models.catalog():
        if models.installed(model):
            return model
    return next(iter(models.catalog()), 'nymphaea')


def resolve_persona(parameters):
    """A stored character, or an inline sheet for a client that keeps nothing."""
    identifier = (parameters.get('persona_id') or '').strip()
    if identifier:
        return library.personas.get(identifier), identifier
    inline = parameters.get('persona')
    if inline:
        return normalize_persona(inline), ''
    stored = library.personas.list()
    if len(stored) == 1:
        return library.personas.get(stored[0]['id']), stored[0]['id']
    raise CyToolError('InvalidParameters',
                      'Give persona_id, or an inline persona. '
                      + ('No character is stored yet; create one first.' if not stored
                         else 'Stored characters: ' + ', '.join(p['id'] for p in stored[:20])))


def resolve_world(persona, parameters):
    identifier = (parameters.get('world_id') or persona.get('world_id') or '').strip()
    if identifier and library.worlds.exists(identifier):
        return library.worlds.get(identifier), identifier
    return None, identifier


def generation_settings(persona, parameters):
    """The sheet's own settings, with per-call overrides applied on top."""
    generation = dict(persona.get('generation') or {})
    settings = {
        'llm_model': (parameters.get('llm_model') or generation.get('llm_model') or '').strip(),
        'device': (parameters.get('device') or generation.get('device') or 'cpu').strip(),
        'temperature': parameters.get('temperature') if parameters.get('temperature') is not None
        else generation.get('temperature', 0.85),
        'top_p': generation.get('top_p', 0.95),
        'repeat_penalty': generation.get('repeat_penalty', 1.08),
        'response_length': parameters.get('response_length') if parameters.get('response_length') is not None
        else generation.get('response_length', 400),
        'seed': parameters.get('seed') if parameters.get('seed') is not None
        else generation.get('seed', -1),
        'threads': parameters.get('threads') if parameters.get('threads') is not None
        else generation.get('threads', 4),
        'keep_loaded': bool(parameters.get('keep_loaded')),
    }
    if not settings['llm_model'] or settings['llm_model'] not in models.catalog():
        settings['llm_model'] = _first_installed()
    return settings


def create_runtime(data_dir, **options):
    ensure_data_layout()
    manifest = load_manifest(APP / 'CyTool.json')
    catalog = models.catalog()
    for backend in manifest.get('backends', []):
        backend['models'] = [{'id': model, 'name': catalog[model]['name'],
                              'version': catalog[model].get('revision', '')[:12] or '1',
                              'installed': models.installed(model)} for model in catalog]
    runtime = Runtime(manifest, data_dir, **options)
    runtime.configure_inputs(DATA / 'inputs',
                             fields={'import_personas': ['file'], 'transcribe': ['audio'],
                                     'speak_batch_file': ['file', 'personas.*'],
                                     'create_stable_voice': ['audio'],
                                     'add_persona_image': ['image']})
    resident = ResidentModel(runtime)
    runtime.resident_model = resident
    voice_runner.bind(runtime)

    # ------------------------------------------------------------------ chat

    def _run_model(context, settings, items, **options):
        return resident.generate(context, settings, items, **options)

    def _direct(context, persona, world, reply, user_text, settings):
        """Second pass. A failure here must never lose a reply that already succeeded."""
        from personarp.prompting import director_messages
        media = persona['media']
        schema = scene.director_schema(media)
        budget = {'minimal': 400, 'standard': 700, 'full': 1100}.get(media.get('detail', 'standard'), 700)
        # Always keep_loaded here: the caller's preference is applied once, after this pass.
        director = {**settings, 'temperature': min(0.7, settings['temperature']),
                    'response_length': budget, 'keep_loaded': True}
        chosen = (media.get('director_model') or '').strip()
        if chosen and chosen in models.catalog():
            if not models.installed(chosen):
                return None, ('The description model "%s" is not installed; install it in Models '
                              'or clear it on the sheet.' % chosen)
            director['llm_model'] = chosen
        try:
            answer = _run_model(context, director,
                                director_messages(persona, reply, user_text, world),
                                json_schema=schema, progress=(62, 68))
            return scene.sanitize_directive(json.loads(answer['text'])), ''
        except CyToolError as exc:
            if exc.code in ('Cancelled', 'Timeout'):
                raise
            return None, 'Scene description unavailable: ' + str(exc)
        except ValueError as exc:
            return None, 'Scene description was not valid JSON: ' + str(exc)

    # --------------------------------------------------- free discussion threads

    def _assistant_settings(document, parameters):
        """The thread's own settings, with per-call overrides, then a sensible default."""
        model = (parameters.get('llm_model') or document.get('llm_model') or '').strip()
        if not model or model not in models.catalog() or not models.installed(model):
            model = _first_installed()
        device = (parameters.get('device') or document.get('device') or '').strip()
        if not device:
            device = 'cuda' if models.engine_status()['cuda']['installed'] else 'cpu'
        return {'llm_model': model, 'device': device,
                'temperature': parameters.get('temperature')
                if parameters.get('temperature') is not None
                else document.get('temperature', 0.7),
                'top_p': 0.95, 'repeat_penalty': 1.08,
                'response_length': int(parameters.get('response_length')
                                       or document.get('response_length') or 800),
                'seed': -1, 'threads': 8,
                'keep_loaded': bool(parameters.get('keep_loaded'))}

    def assistant_chat(context, parameters):
        """One turn of free discussion. The thread is written before the reply is returned."""
        with exclusive(context):
            if not str(parameters.get('text', '')).strip():
                raise CyToolError('InvalidParameters', 'The message is empty.')
            identifier = (parameters.get('thread_id') or '').strip()
            document = assistant.get(identifier) if identifier else assistant.create()
            if parameters.get('system'):
                document['system'] = parameters['system']
            settings = _assistant_settings(document, parameters)
            document.update(llm_model=settings['llm_model'], device=settings['device'],
                            temperature=settings['temperature'],
                            response_length=settings['response_length'])

            message = parameters['text']
            described, picture = _picture_context(context, parameters, progress=(5, 18))
            if described:
                message += ('\n\n[Image fournie. Ce qu elle montre, lu par le modele de '
                            'vision :]\n' + described)

            budget = int(parameters.get('context_budget') or 12000)
            kept, dropped = prompting.trim_history(assistant.history(document), budget)
            items = [{'role': 'system', 'content': document['system']}, *kept,
                     {'role': 'user', 'content': message}]
            answer = _run_model(context, settings, items)

            if not document.get('turns') and not parameters.get('title'):
                document['title'] = assistant.suggest_title(parameters['text'])
            if parameters.get('title'):
                document['title'] = parameters['title']
            assistant.append(document, 'user', message)
            assistant.append(document, 'assistant', answer['text'])
            document['draft'] = ''
            assistant.save(document)

            path = context.path('outputs/reply.txt')
            path.write_text(answer['text'], encoding='utf-8')
            context.progress(100, currentStep='Reply ready')
            return {'text': answer['text'], 'threadId': document['id'],
                    'title': document['title'], 'turns': document['turns'],
                    'seconds': answer['seconds'], 'reused': answer['reused'],
                    'truncated': bool(answer.get('truncated')),
                    'picture': picture,
                    'context': {'droppedMessages': dropped, 'model': settings['llm_model'],
                                'device': settings['device'], **answer.get('window', {})},
                    'file': str(path), 'mimeType': 'text/plain'}

    def list_assistant_threads(context, parameters):
        return {'threads': assistant.listing()}

    def new_assistant_thread(context, parameters):
        document = assistant.create(parameters.get('title', ''), parameters.get('system', ''))
        return {'thread': document, 'id': document['id']}

    def get_assistant_thread(context, parameters):
        document = assistant.get(parameters['thread_id'])
        return {'thread': document, 'file': str(assistant.path_for(document['id']))}

    def save_assistant_thread(context, parameters):
        """Keep the draft and the settings of a thread without sending anything."""
        document = assistant.get(parameters['thread_id'])
        for key in ('title', 'system', 'draft', 'llm_model', 'device'):
            if parameters.get(key) is not None:
                document[key] = parameters[key]
        for key in ('temperature', 'response_length'):
            if parameters.get(key) is not None:
                document[key] = parameters[key]
        return {'thread': assistant.save(document)}

    def remove_assistant_thread(context, parameters):
        return assistant.remove(parameters['thread_id'])

    # ------------------------------------------------------------- photographs

    def add_persona_image(context, parameters):
        source = Path(parameters['image'])
        if not source.is_absolute():
            source = DATA / 'inputs' / parameters['image']
        persona = library.personas.get(parameters['persona_id'])
        persona = imaging.add(persona, source, parameters.get('role', 'reference'),
                              parameters.get('caption', ''))
        saved = library.personas.save(persona)
        return {'persona': saved, 'references': saved['references'],
                'file': saved['references'][-1]['file']}

    def remove_persona_image(context, parameters):
        persona = library.personas.get(parameters['persona_id'])
        persona, moved = imaging.remove(persona, parameters['file'])
        saved = library.personas.save(persona)
        return {'persona': saved, 'references': saved['references'], 'trash': moved}

    def verify_persona_images(context, parameters):
        persona = library.personas.get(parameters['persona_id'])
        return {'references': imaging.verify(persona)}

    def list_images(context, parameters):
        return {'images': imaging.library_listing((parameters.get('persona_id') or '').strip())}

    def _resolve_image(parameters, persona):
        """The picture to read: a loose file, a photograph of the sheet, or the first one."""
        loose = (parameters.get('image') or '').strip()
        if loose:
            path = Path(loose)
            if not path.is_absolute():
                path = DATA / 'inputs' / loose
            if not path.is_file():
                raise CyToolError('MissingInput', 'Image not found: ' + str(path))
            return str(path), None
        path = (parameters.get('file') or '').strip()
        references = (persona or {}).get('references') or []
        if path:
            return path, next((item for item in references if item.get('file') == path), None)
        if references:
            return references[0]['file'], references[0]
        raise CyToolError('InvalidParameters',
                          'Give an image, or add a photograph to the sheet first.')

    def _vision_model(parameters):
        chosen = (parameters.get('llm_model') or '').strip()
        available = models.vision_models()
        if chosen and not models.is_vision(chosen):
            raise CyToolError('InvalidParameters',
                              '"%s" cannot read an image. Installed vision models: %s'
                              % (chosen, ', '.join(available) or 'none'))
        chosen = chosen or (available[0] if available else '')
        if not chosen:
            raise CyToolError(
                'MissingModel',
                'No vision model is installed. Install one in Models — they are the entries '
                'marked as reading images.')
        return chosen

    def _read_picture(context, path, persona, reference, parameters, progress=(10, 30)):
        """Read a picture in two passes: look, then write. Returns the appearance fields.

        The first pass sends the photograph and lets the model describe it in prose; the
        second, text only on the model already loaded, writes the sheet from that
        observation under a schema that asks for phrases. See authoring.VISION_SYSTEM.
        Returns (fields, model, encoded picture, answer, observation).
        """
        chosen = _vision_model(parameters)
        context.progress(progress[0] - 5, currentStep='Preparing the picture')
        encoded = imaging.encoded(path)
        existing = None
        if parameters.get('use_existing', True) and persona:
            existing = {k: v for k, v in (persona.get('appearance') or {}).items()
                        if v and k in authoring.VISION_FIELDS}
        role = (reference or {}).get('role', '')
        caption = (reference or {}).get('caption', '')
        base = {**generation_settings(persona or normalize_persona({}), {}),
                'llm_model': chosen, 'temperature': 0.3,
                'device': parameters.get('device') or 'cuda'}
        middle = (progress[0] + progress[1]) // 2

        # Look: the photograph, free prose. The weights stay loaded for the second pass.
        looked = _run_model(context, {**base, 'response_length': 900, 'keep_loaded': True},
                            [{'role': 'system', 'content': authoring.VISION_SYSTEM},
                             {'role': 'user', 'content': [
                                 {'type': 'text',
                                  'text': authoring.observation_request(role, caption)},
                                 {'type': 'image_url', 'image_url': {'url': encoded['url']}}]}],
                            progress=(progress[0], middle), fit=False)
        observation = (looked.get('text') or '').strip()
        if not observation:
            raise CyToolError('InvalidResponse', 'The vision model saw nothing to describe.')

        # Write: text only, constrained, in the language of the sheet.
        context.progress(middle, currentStep='Writing the appearance')
        request = authoring.vision_request(
            role, caption, parameters.get('language')
            or ((persona or {}).get('generation') or {}).get('language', 'Francais'),
            existing, observation)
        answer = _run_model(context, {**base, 'temperature': 0.2, 'response_length': 1400,
                                      'keep_loaded': bool(parameters.get('keep_loaded'))},
                            [{'role': 'system', 'content': authoring.VISION_STRUCTURE_SYSTEM},
                             {'role': 'user', 'content': request}],
                            json_schema=authoring.vision_schema(),
                            progress=(middle, progress[1]), fit=False)
        try:
            fields = json.loads(answer['text'])
        except ValueError as exc:
            raise CyToolError('InvalidResponse',
                              'The vision model did not return JSON: ' + str(exc)) from exc
        language = parameters.get('language') \
            or ((persona or {}).get('generation') or {}).get('language', 'Francais')
        fields = authoring.clean_vision_fields(
            {k: v for k, v in fields.items() if k in authoring.VISION_FIELDS and v}, language)
        fields = {k: v for k, v in fields.items() if v}
        answer = {**answer, 'seconds': round(float(looked.get('seconds') or 0)
                                             + float(answer.get('seconds') or 0), 3)}
        return fields, chosen, encoded, answer, observation

    def _picture_as_text(fields):
        """The description a writing model can actually use, as plain prose."""
        lines = []
        for key in authoring.VISION_FIELDS:
            value = fields.get(key)
            if not value:
                continue
            lines.append('%s: %s' % (key, ', '.join(value) if isinstance(value, list) else value))
        return '\n'.join(lines)

    def describe_image(context, parameters):
        """Read a photograph with a vision model and write the appearance branch."""
        with exclusive(context):
            persona, persona_id = (None, '')
            if parameters.get('persona_id') or parameters.get('persona') \
                    or not (parameters.get('image') or '').strip():
                persona, persona_id = resolve_persona(parameters)
            path, reference = _resolve_image(parameters, persona)

            proposal, chosen, encoded, answer, observation = _read_picture(
                context, path, persona, reference, parameters)
            output = context.path('outputs/appearance.json')
            write_json(output, proposal)
            context.progress(100, currentStep='Appearance described')
            return {'proposal': proposal, 'text': _picture_as_text(proposal),
                    'observation': observation,
                    'target': 'appearance', 'kind': 'persona',
                    'model': chosen, 'source': path, 'seconds': answer['seconds'],
                    'sentWidth': encoded['sentWidth'], 'sentHeight': encoded['sentHeight'],
                    'file': str(output)}

    def _picture_context(context, parameters, persona=None, progress=(5, 20)):
        """Describe a supplied picture and return it as text for a writing model."""
        loose = (parameters.get('image') or '').strip()
        if not loose:
            return '', {}
        path, reference = _resolve_image(parameters, persona)
        fields, chosen, encoded, answer, observation = _read_picture(
            context, path, persona, reference,
            {**parameters, 'llm_model': parameters.get('vision_model', ''),
             'use_existing': False, 'keep_loaded': True}, progress=progress)
        # The writing model gets both: the fields, and the fuller observation behind them.
        described = _picture_as_text(fields) + '\n\nObservation of the picture:\n' + observation
        return described, {'model': chosen, 'source': path, 'seconds': answer['seconds'],
                           'fields': sorted(fields)}

    # ----------------------------------------------------------------- voice

    def _render_voice(context, persona, text, world, user_text, directive,
                      offset=0.0, scale=1.0, overrides=None):
        """Speak a line with this character's voice. Returns the worker result plus a note."""
        if not text.strip():
            raise CyToolError('InvalidParameters', 'There is nothing to speak.')
        overrides = overrides or {}
        payload, note = voice_delivery.payload_for(
            persona, text, world=world, user_text=user_text, scene=directive,
            model=overrides.get('model', ''), device=overrides.get('device', 'cuda'),
            seed=overrides.get('seed'), delivery=overrides.get('delivery', ''),
            language=overrides.get('language', ''))
        plan = payload.pop('voice_plan', {})
        payload['workspace'] = str(context.workspace)
        payload['output_dir'] = 'outputs/voice'
        result = voice_runner.speak(context, payload, offset=offset, scale=scale)
        result['note'] = note
        result['voicePlan'] = plan
        result['language'] = payload.get('language', 'Auto')
        result['mimeType'] = 'audio/wav'
        return result

    def speak(context, parameters):
        with exclusive(context):
            persona = normalize_persona({})
            world = None
            if parameters.get('persona_id'):
                persona = library.personas.get(parameters['persona_id'])
                world, _ = resolve_world(persona, parameters)
            if parameters.get('voice'):
                persona = {**persona, 'voice': {**persona['voice'], **parameters['voice']}}
            if parameters.get('voice_id'):
                persona = {**persona, 'voice': {**persona['voice'],
                                                'voice_id': parameters['voice_id']}}
            result = _render_voice(context, persona, parameters['text'], world, '', None,
                                   overrides=parameters)
            context.progress(100, currentStep='Take ready')
            return result

    DEFAULT_TAKE = (
        "Bonjour. Je m'appelle {name}. Voici ma voix telle qu'elle sonnera désormais, "
        "dans les scènes calmes comme dans les moments tendus. "
        "Écoutez le grain, le rythme, la façon dont je marque les silences. "
        "Si cette voix vous convient, gardez-la : toutes mes répliques la reprendront.")
    # A take for another language has to be read in that language, or the voice it gives
    # is the character's own voice again. Roughly the same length in every language.
    DEFAULT_TAKES = {
        'French': DEFAULT_TAKE,
        'English': (
            "Hello. My name is {name}. This is my voice as it will sound from now on, in quiet "
            "scenes as well as in tense moments. Listen to the grain, the rhythm, the way I "
            "hold a silence. If this voice suits you, keep it: every line I speak will use it."),
        'Spanish': (
            "Hola. Me llamo {name}. Esta es mi voz tal como sonará a partir de ahora, en las "
            "escenas tranquilas y en los momentos tensos. Escucha el timbre, el ritmo, la "
            "manera en que marco los silencios. Si esta voz te convence, guárdala: todas mis "
            "réplicas la usarán."),
        'German': (
            "Hallo. Ich heiße {name}. So wird meine Stimme von nun an klingen, in ruhigen "
            "Szenen genauso wie in angespannten Momenten. Hör auf die Klangfarbe, den "
            "Rhythmus, die Art, wie ich eine Pause halte. Wenn dir diese Stimme gefällt, "
            "behalte sie: jeder meiner Sätze wird sie verwenden."),
        'Italian': (
            "Ciao. Mi chiamo {name}. Questa è la mia voce, come suonerà d'ora in poi, nelle "
            "scene tranquille come nei momenti di tensione. Ascolta il timbro, il ritmo, il "
            "modo in cui tengo un silenzio. Se questa voce ti piace, tienila: ogni mia battuta "
            "la userà."),
        'Portuguese': (
            "Olá. O meu nome é {name}. Esta é a minha voz tal como vai soar a partir de agora, "
            "nas cenas calmas e nos momentos tensos. Ouve o timbre, o ritmo, a forma como "
            "seguro um silêncio. Se esta voz te agrada, guarda-a: todas as minhas falas vão "
            "usá-la."),
        'Russian': (
            "Здравствуйте. Меня зовут {name}. Так будет звучать мой голос с этого момента, в "
            "спокойных сценах и в напряжённые минуты. Послушайте тембр, ритм, то, как я "
            "держу паузу. Если этот голос вам подходит, оставьте его: все мои реплики будут "
            "звучать так."),
        'Chinese': (
            "你好。我叫{name}。从现在开始，我的声音就是这样，无论是在平静的场景，还是在紧张的时刻。"
            "请听我的音色、节奏，还有我停顿的方式。如果你喜欢这个声音，就把它留下来，"
            "我以后的每一句台词都会用它。"),
        'Japanese': (
            "こんにちは。私の名前は{name}です。これからの私の声はこのように聞こえます。"
            "静かな場面でも、緊迫した瞬間でも同じです。声の質感、リズム、そして間の取り方を"
            "聞いてください。この声が気に入ったら、残してください。私のすべてのセリフがこの声になります。"),
        'Korean': (
            "안녕하세요. 제 이름은 {name}입니다. 앞으로 제 목소리는 이렇게 들릴 거예요. "
            "조용한 장면에서도, 긴장된 순간에도 마찬가지입니다. 음색과 리듬, 그리고 제가 "
            "침묵을 두는 방식을 들어 보세요. 이 목소리가 마음에 드시면 간직해 주세요. "
            "제 모든 대사가 이 목소리로 나올 거예요."),
    }

    def capture_voice_take(context, parameters):
        """Produce the ~12–24 s reference a stable voice is then built from."""
        with exclusive(context):
            persona = normalize_persona({})
            world = None
            if parameters.get('persona_id'):
                persona = library.personas.get(parameters['persona_id'])
                world, _ = resolve_world(persona, parameters)
            voice = dict(persona['voice'])
            if parameters.get('description'):
                voice['description'] = parameters['description']
            if parameters.get('speaker'):
                voice['speaker'] = parameters['speaker']
                voice['description'] = ''
            if parameters.get('language'):
                voice['language'] = parameters['language']
            # A take is a sample of the voice, not a scene: no stable voice, no annotations, and
            # no per-language voice either — a take in English must be the voice described
            # here, not the English voice the sheet may already use.
            voice['voice_id'] = ''
            voice['languages'] = []
            voice['annotations'] = False
            persona = {**persona, 'voice': voice}
            language = voice.get('language') or 'Auto'
            text = (parameters.get('text') or '').strip() or \
                DEFAULT_TAKES.get(language, DEFAULT_TAKE).format(
                    name=persona.get('name') or ('ce personnage' if language in ('Auto', 'French')
                                                 else 'this character'))
            result = _render_voice(context, persona, text, world, '', None, offset=0.0, scale=0.7,
                                   overrides={**parameters, 'delivery': 'complete'})
            transcript = text
            if parameters.get('transcribe'):
                context.progress(72, currentStep='Transcribing the take')
                heard = voice_runner.transcribe(
                    context, {'model_dir': _whisper_directory(), 'input': result['file'],
                              'device': parameters.get('device', 'cuda'), 'timestamps': False},
                    offset=72.0, scale=0.25)
                transcript = heard['text'] or text
            # A job workspace is private and short-lived; a take you may want to register
            # tomorrow has to outlive it, so keep a copy beside the voice library.
            takes = voice_stable.VOICES / 'takes'        # beside the voices, wherever they live
            takes.mkdir(parents=True, exist_ok=True)
            kept = takes / ('take-' + library.now().replace(':', '') + '.wav')
            shutil.copyfile(result['file'], kept)

            seconds = float(result.get('durationSeconds', 0.0))
            low, high = voice_stable.IDEAL_SECONDS
            in_range = low <= seconds <= high
            advice = '' if in_range else (
                'This take is %.1f s. Between %.0f and %.0f seconds gives the steadiest clone: '
                '%s the text and capture again.'
                % (seconds, low, high, 'lengthen' if seconds < low else 'shorten'))
            context.progress(100, currentStep='Take ready')
            return {'file': str(kept), 'workspaceFile': result['file'], 'transcript': transcript,
                    'durationSeconds': seconds, 'inRange': in_range, 'advice': advice,
                    'mode': result.get('mode', ''), 'model': result.get('model', ''),
                    'language': result.get('language', 'Auto'), 'mimeType': 'audio/wav'}

    def _whisper_directory():
        for model, info in voice_catalog.catalog().items():
            if info.get('backend') == 'whisper' and voice_catalog.installed(model):
                return str(voice_catalog.directory(model))
        raise CyToolError('MissingModel',
                          'Whisper is not installed; install it in Voice, or type the exact '
                          'words of the take yourself.')

    def create_stable_voice(context, parameters):
        with exclusive(context):
            source = Path(parameters['audio'])
            if not source.is_absolute():
                source = DATA / 'inputs' / parameters['audio']
            if not source.is_file():
                raise CyToolError('MissingInput', 'Recording not found: ' + str(source))
            transcript = (parameters.get('transcript') or '').strip()
            if parameters.get('transcribe') or not transcript:
                if not parameters.get('transcribe') and not transcript:
                    context.progress(5, currentStep='Transcribing the recording')
                heard = voice_runner.transcribe(
                    context, {'model_dir': _whisper_directory(), 'input': str(source),
                              'device': parameters.get('device', 'cuda'), 'timestamps': False},
                    offset=5.0, scale=0.8)
                transcript = heard['text'] or transcript
            document = voice_stable.create(
                parameters['name'], source, transcript,
                persona_id=parameters.get('persona_id', ''),
                model=parameters.get('model') or voice_delivery.CLONE_VARIANT,
                source=parameters.get('source', 'generated'),
                language=parameters.get('language', 'Auto'),
                description=parameters.get('description', ''))
            attached = False
            for_language = (parameters.get('for_language') or '').strip()
            if parameters.get('attach', True) and parameters.get('persona_id'):
                persona = library.personas.get(parameters['persona_id'])
                if for_language == voice_delivery.native_language(persona):
                    for_language = ''           # its own language: that is the main voice
                if for_language:
                    # A voice for one language sits beside the main voice, never over it.
                    entries = [entry for entry in persona['voice'].get('languages') or []
                               if entry.get('language') != for_language]
                    previous = next((entry for entry in persona['voice'].get('languages') or []
                                     if entry.get('language') == for_language), {})
                    entries.append({**previous, 'language': for_language, 'source': 'voice',
                                    'voice_id': document['id']})
                    persona['voice'] = {**persona['voice'], 'languages': entries}
                else:
                    persona['voice'] = {**persona['voice'], 'voice_id': document['id'],
                                        'enabled': True, 'model': document['model']}
                library.personas.save(persona)
                attached = True
            low, high = voice_stable.IDEAL_SECONDS
            warning = '' if low <= document['reference_seconds'] <= high else (
                'The reference is %.1f s; %.0f to %.0f seconds clones more steadily.'
                % (document['reference_seconds'], low, high))
            context.progress(100, currentStep='Stable voice registered')
            return {'voice': document, 'id': document['id'], 'attached': attached,
                    'forLanguage': for_language if attached else '', 'warning': warning}

    def list_voices(context, parameters):
        return {'voices': voice_stable.listing((parameters.get('persona_id') or '').strip())}

    def verify_voice(context, parameters):
        return voice_stable.verify(parameters['voice_id'])

    def remove_voice(context, parameters):
        return voice_stable.remove(parameters['voice_id'])

    def transcribe(context, parameters):
        with exclusive(context):
            source = Path(parameters['audio'])
            if not source.is_absolute():
                source = DATA / 'inputs' / parameters['audio']
            if not source.is_file():
                raise CyToolError('MissingInput', 'Recording not found: ' + str(source))
            result = voice_runner.transcribe(
                context, {'model_dir': _whisper_directory(), 'input': str(source),
                          'device': parameters.get('device', 'cuda'),
                          'language': parameters.get('language', ''),
                          'timestamps': parameters.get('timestamps', True)})
            path = context.path('outputs/transcript.json')
            write_json(path, result)
            result['file'] = str(path)
            return result

    def list_voice_models(context, parameters):
        return {'models': voice_catalog.catalog_status(bool(parameters.get('verify')), context),
                **voice_runner.diagnose(context)}

    def install_voice_model(context, parameters):
        with exclusive(context):
            return voice_catalog.install(context, parameters)

    def install_voice_engine(context, parameters):
        with exclusive(context):
            voice_runner.release()
            return voice_catalog.install_engine(context, parameters)

    def release_voice(context, parameters):
        with exclusive(context):                # after the voice being spoken, not during
            return voice_runner.release()

    def chat(context, parameters):
        with exclusive(context):
            if not str(parameters.get('text', '')).strip():
                raise CyToolError('InvalidParameters', 'The message is empty.')
            persona, persona_id = resolve_persona(parameters)
            world, _ = resolve_world(persona, parameters)
            want = parameters.get('want_scene', 'auto')
            if want != 'auto':
                persona = copy.deepcopy(persona)
                persona['media'] = {**persona['media'], 'enabled': want == 'yes'}
            others = []
            if parameters.get('include_cast', True) and persona.get('world_id'):
                others = [entry for entry in library.cast(persona['world_id'])
                          if entry['id'] != persona_id]

            session = None
            history = parameters.get('history') or []
            session_id = (parameters.get('session_id') or '').strip()
            if session_id:
                if not persona_id:
                    raise CyToolError('InvalidParameters',
                                      'A session belongs to a stored character; give persona_id.')
                session = sessions.get(persona_id, session_id)
                history = sessions.history(session)

            settings = generation_settings(persona, parameters)
            needs_director = bool(persona['media'].get('enabled')) \
                and persona['media'].get('mode', 'director') != 'inline'
            built = build_messages(persona, parameters['text'], history, world, others)
            # Hold the weights across the two passes even when the caller did not ask to keep
            # them; releasing between passes would reload the model for a 700-token describe.
            answer = _run_model(context, {**settings, 'keep_loaded': True} if needs_director
                                else settings, built['messages'])

            media = persona['media']
            wants_scene = bool(media.get('enabled'))
            inline = media.get('mode', 'director') == 'inline'
            parsed = scene.split_reply(answer['text'], expect_scene=wants_scene and inline)

            # Director pass: a second, schema-constrained generation reads the line that was
            # just played and describes the shot. The roleplay model is never asked to emit
            # JSON, so the dialogue stays clean and the directive is always parseable.
            if needs_director:
                context.progress(60, currentStep='Describing the shot')
                try:
                    directive, error = _direct(context, persona, world, answer['text'],
                                               parameters['text'], settings)
                finally:
                    if not settings.get('keep_loaded'):
                        resident.stop()
                if directive:
                    parsed = {**parsed, 'scene': directive, 'scene_error': error, 'raw_scene': ''}
                elif error:
                    parsed = {**parsed, 'scene_error': error}
            if parsed['scene']:
                parsed['scene'] = {**parsed['scene'], 'persona_id': persona_id,
                                   'persona_name': persona.get('name', ''),
                                   'duration_seconds': parsed['scene'].get('duration_seconds')
                                   or float(media.get('duration_seconds', 5.0)),
                                   'aspect_ratio': parsed['scene'].get('aspect_ratio')
                                   or media.get('aspect_ratio', '16:9')}
            voice = persona['voice']
            annotations = scene.parse_annotations(parsed['text'])
            spoken = scene.spoken_text(parsed['text'],
                                       keep_annotations=bool(voice.get('annotations')),
                                       speak_narration=bool(voice.get('speak_narration')))
            prompts = scene.to_prompts(parsed['scene'], persona, world)

            context.progress(92, currentStep='Reply parsed')
            outputs = {
                'text': answer['text'],
                'dialogue': scene.strip_annotations(parsed['text']),
                'spoken': spoken,
                'scene': parsed['scene'] or {},
                'sceneError': parsed['scene_error'],
                'rawScene': parsed['raw_scene'],
                'prompts': prompts,
                'annotations': annotations,
                'audioFile': '', 'voiceError': '',
                'context': {**built['context'], **answer.get('window', {}),
                            'persona': persona_id, 'world': (world or {}).get('id', ''),
                            'model': settings['llm_model'], 'device': settings['device']},
                'seconds': answer['seconds'], 'reused': answer['reused'],
            }

            wants_audio = parameters.get('speak', 'auto')
            if wants_audio == 'yes' or (wants_audio == 'auto' and voice.get('enabled')):
                # A failed take must never cost a reply that already succeeded.
                try:
                    context.progress(80, currentStep='Speaking the reply')
                    take = _render_voice(context, persona, spoken, world, parameters['text'],
                                         parsed['scene'], offset=80.0, scale=0.18)
                    outputs['audioFile'] = take['file']
                    outputs['audio'] = {k: take[k] for k in
                                        ('durationSeconds', 'sampleRate', 'mode', 'model',
                                         'segments', 'generationSeconds') if k in take}
                    if take.get('note'):
                        outputs['voiceError'] = take['note']
                except CyToolError as exc:
                    if exc.code in ('Cancelled', 'Timeout'):
                        raise
                    outputs['voiceError'] = str(exc)

            turns = [*history, {'role': 'user', 'content': parameters['text']},
                     {'role': 'assistant', 'content': answer['text']}]
            outputs['history'] = turns
            if session is not None and parameters.get('save', True):
                sessions.append_turn(session, 'user', parameters['text'])
                sessions.append_turn(session, 'assistant', answer['text'],
                                     scene=parsed['scene'], annotations=annotations,
                                     prompts=prompts, model=settings['llm_model'])
                sessions.save(session)
                outputs['sessionId'] = session['id']
                outputs['sessionFile'] = str(sessions.path(persona_id, session['id']))

            reply_file = context.path('outputs/reply.txt')
            reply_file.write_text(answer['text'], encoding='utf-8')
            write_json(context.path('outputs/turn.json'), outputs)
            if parsed['scene']:
                write_json(context.path('outputs/scene.json'),
                           {**parsed['scene'], **prompts})
            outputs['file'] = str(reply_file)
            outputs['mimeType'] = 'text/plain'
            context.progress(100, currentStep='Reply ready')
            return outputs

    def preview_prompt(context, parameters):
        persona, persona_id = resolve_persona(parameters)
        world, _ = resolve_world(persona, parameters)
        others = []
        if parameters.get('include_cast', True) and persona.get('world_id'):
            others = [entry for entry in library.cast(persona['world_id']) if entry['id'] != persona_id]
        history = []
        session_id = (parameters.get('session_id') or '').strip()
        if session_id and persona_id:
            history = sessions.history(sessions.get(persona_id, session_id))
        built = build_messages(persona, parameters.get('text', ''), history, world, others)
        path = context.path('outputs/prompt.json')
        write_json(path, built)
        return {'messages': built['messages'], 'prompt': chatml(built['messages']),
                'context': built['context'], 'file': str(path)}

    # ---------------------------------------------------------------- authoring

    def author(context, parameters):
        with exclusive(context):
            kind = parameters.get('kind', 'persona')
            current = None
            if kind == 'persona' and parameters.get('persona_id'):
                current = library.personas.get(parameters['persona_id'])
            elif kind == 'world' and parameters.get('world_id'):
                current = library.worlds.get(parameters['world_id'])
            request = parameters['request']
            described, picture = _picture_context(context, parameters, current, progress=(4, 16))
            if described:
                request += ('\n\nUne image de reference a ete fournie. Ce qu elle montre, lu '
                            'par le modele de vision :\n' + described)
            thread = (parameters.get('thread_id') or '').strip()
            if thread:
                discussion = assistant.as_context(assistant.get(thread))
                if discussion:
                    request += ('\n\nCe qui a ete dit dans la discussion preparatoire :\n'
                                + discussion)
            plan = authoring.parameters(request, parameters.get('target', 'sheet'),
                                        current, kind, parameters.get('language', 'Francais'))
            blank = normalize_persona({})
            blank['generation'] = {
                **blank['generation'], 'system_prompt': plan['system'],
                'language': parameters.get('language', 'Francais'),
                'response_length': int(parameters.get('response_length') or 2048),
                'temperature': 0.7,
                # The assistant has no sheet of its own, so without this it would inherit the
                # blank default and quietly run on the processor.
                'device': _assistant_device(parameters, current),
                'llm_model': (parameters.get('llm_model') or '').strip()
                or _assistant_model(current)}
            blank['enabled'] = False
            blank['media'] = {**blank['media'], 'enabled': False}
            blank['voice'] = {**blank['voice'], 'enabled': False}
            settings = generation_settings(blank, parameters)
            built = build_messages(blank, plan['text'], [], None, None)
            # Constrained like the other structured passes: a proposal that does not parse is
            # a failure the user can do nothing about.
            schema = None if plan['plain'] else authoring.grammar_schema(plan['target'], kind)
            answer = _run_model(context, settings, built['messages'], json_schema=schema)
            if answer.get('truncated'):
                raise CyToolError(
                    'ResponseTruncated',
                    'The proposal was cut off at %d tokens. Ask for fewer sections, or raise '
                    'the reply length in Advanced.' % settings['response_length'],
                    recoverable=True)
            proposal = authoring.parse_proposal(answer['text'], plan['target'], kind)
            path = context.path('outputs/proposal.json')
            write_json(path, {'proposal': proposal, 'target': plan['target'], 'kind': kind})
            context.progress(100, currentStep='Proposal ready')
            return {'proposal': proposal, 'raw': answer['text'], 'target': plan['target'],
                    'kind': kind, 'seconds': answer['seconds'], 'picture': picture,
                    'file': str(path)}

    def _assistant_device(parameters, current):
        """The device the assistant really runs on: what was asked, else the character's own,
        else the GPU when a CUDA engine is installed."""
        asked = (parameters.get('device') or '').strip()
        if asked:
            return asked
        if current and (current.get('generation') or {}).get('device'):
            return current['generation']['device']
        return 'cuda' if models.engine_status()['cuda']['installed'] else 'cpu'

    def _assistant_model(current):
        """Writing a sheet is a structured task; prefer the character's model, else any
        installed one rather than the catalogue's first entry."""
        if current and (current.get('generation') or {}).get('llm_model'):
            chosen = current['generation']['llm_model']
            if models.installed(chosen):
                return chosen
        return _first_installed()

    def apply_proposal(context, parameters):
        kind = parameters.get('kind', 'persona')
        target = parameters.get('target', 'sheet')
        if kind == 'persona':
            identifier = (parameters.get('persona_id') or '').strip()
            document = library.personas.get(identifier) if identifier else normalize_persona({})
            merged = authoring.apply_proposal(document, parameters['proposal'], target, kind)
            saved = library.personas.save(merged) if identifier else library.personas.create(merged)
        else:
            identifier = (parameters.get('world_id') or '').strip()
            document = library.worlds.get(identifier) if identifier else normalize_world({})
            merged = authoring.apply_proposal(document, parameters['proposal'], target, kind)
            saved = library.worlds.save(merged) if identifier else library.worlds.create(merged)
        return {'document': saved, 'id': saved['id'], 'revision': saved['revision']}

    # ------------------------------------------------------------------ library

    def list_personas(context, parameters):
        world_id = (parameters.get('world_id') or '').strip()
        return {'personas': library.cast(world_id) if world_id else library.personas.list()}

    def get_persona(context, parameters):
        persona = library.personas.get(parameters['persona_id'])
        world, _ = resolve_world(persona, parameters)
        return {'persona': persona, 'world': world or {},
                'file': str(library.personas.path(persona['id']))}

    def create_persona(context, parameters):
        document = normalize_persona(parameters.get('persona') or {})
        if parameters.get('name'):
            document['name'] = parameters['name']
        saved = library.personas.create(document)
        return {'persona': saved, 'id': saved['id'], 'file': str(library.personas.path(saved['id']))}

    def save_persona(context, parameters):
        saved = library.personas.save(parameters['persona'])
        return {'persona': saved, 'id': saved['id'], 'revision': saved['revision'],
                'file': str(library.personas.path(saved['id']))}

    def duplicate_persona(context, parameters):
        saved = library.personas.duplicate(parameters['persona_id'], parameters.get('name', ''))
        return {'persona': saved, 'id': saved['id']}

    def remove_persona(context, parameters):
        return library.personas.remove(parameters['persona_id'])

    def persona_revisions(context, parameters):
        return {'revisions': library.personas.revisions(parameters['persona_id'])}

    def restore_persona(context, parameters):
        saved = library.personas.restore(parameters['persona_id'], parameters['revision'])
        return {'persona': saved, 'revision': saved['revision']}

    def list_worlds(context, parameters):
        return {'worlds': library.worlds.list()}

    def get_world(context, parameters):
        world = library.worlds.get(parameters['world_id'])
        return {'world': world, 'cast': library.cast(world['id']),
                'file': str(library.worlds.path(world['id']))}

    def create_world(context, parameters):
        document = normalize_world(parameters.get('world') or {})
        if parameters.get('name'):
            document['name'] = parameters['name']
        saved = library.worlds.create(document)
        return {'world': saved, 'id': saved['id'], 'file': str(library.worlds.path(saved['id']))}

    def save_world(context, parameters):
        document = dict(parameters['world'])
        # The lexicon of translated terms changes only through translate and
        # set_term_translations: a window holding an older copy of the world must not wipe
        # the terms learned since it opened it.
        if document.get('id') and library.worlds.exists(document['id']):
            document['term_translations'] = \
                library.worlds.get(document['id']).get('term_translations') or {}
        saved = library.worlds.save(document)
        return {'world': saved, 'id': saved['id'], 'revision': saved['revision'],
                'file': str(library.worlds.path(saved['id']))}

    def remove_world(context, parameters):
        return library.worlds.remove(parameters['world_id'])

    def set_relation(context, parameters):
        persona = library.personas.get(parameters['persona_id'])
        reciprocal = parameters.get('reciprocal')
        if parameters.get('mirror') and not reciprocal:
            reciprocal = {k: v for k, v in parameters['relation'].items()
                          if k in ('type', 'sentiment', 'trust', 'history', 'known')}
        saved = library.set_relation(persona, parameters['relation'], reciprocal)
        return {'persona': saved}

    def drop_relation(context, parameters):
        persona = library.personas.get(parameters['persona_id'])
        return {'persona': library.drop_relation(persona, parameters['target_id'],
                                                 bool(parameters.get('both')))}

    def remember(context, parameters):
        persona = library.personas.get(parameters['persona_id'])
        memory = dict(persona['memory'])
        facts = [str(f).strip() for f in (parameters.get('facts') or []) if str(f).strip()]
        if parameters.get('replace_facts'):
            memory['facts'] = facts
        else:
            memory['facts'] = list(memory.get('facts') or []) + [f for f in facts
                                                                 if f not in (memory.get('facts') or [])]
        episodes = list(memory.get('episodes') or [])
        for episode in parameters.get('episodes') or []:
            if str(episode.get('summary', '')).strip():
                episodes.append(episode)
        memory['episodes'] = episodes
        persona['memory'] = memory
        state = {k: v for k, v in (parameters.get('state') or {}).items()
                 if v not in (None, '', [], {})}
        if state:
            persona['state'] = {**persona['state'], **state, 'updated': library.now()}
        saved = library.personas.save(persona)
        return {'persona': saved,
                'added': len(facts) + len(parameters.get('episodes') or []) + len(state)}

    def export_personas(context, parameters):
        identifiers = parameters.get('persona_ids') or []
        if not identifiers:
            raise CyToolError('InvalidParameters', 'Name at least one character to export.')
        return library.export_bundle(identifiers, parameters.get('destination', ''),
                                     parameters.get('include_world', True),
                                     parameters.get('include_voice', True),
                                     parameters.get('include_audio', False),
                                     parameters.get('include_images', True))

    def list_examples(context, parameters):
        return {'examples': examples.listing(), 'folder': str(examples.EXAMPLES)}

    def import_personas(context, parameters):
        source = Path(parameters['file'])
        if not source.is_absolute():
            source = (DATA / 'inputs' / parameters['file'])
        return library.import_bundle(source, parameters.get('rename', True))

    # ----------------------------------------------------------------- sessions

    def list_sessions(context, parameters):
        return {'sessions': sessions.listing((parameters.get('persona_id') or '').strip())}

    def get_session(context, parameters):
        document = sessions.get(parameters['persona_id'], parameters['session_id'])
        return {'session': document,
                'file': str(sessions.path(parameters['persona_id'], parameters['session_id']))}

    def new_session(context, parameters):
        persona = library.personas.get(parameters['persona_id'])
        document = sessions.create(persona['id'], parameters.get('title', ''))
        document['world_id'] = persona.get('world_id', '')
        sessions.save(document)
        return {'session': document, 'id': document['id']}

    def remove_session(context, parameters):
        return sessions.remove(parameters['persona_id'], parameters['session_id'])

    # -------------------------------------------------------------- translation

    def _translation_settings(persona, parameters):
        """Translation is its own job: its own model, a low temperature, a fixed seed."""
        model = (parameters.get('llm_model') or '').strip()
        if model and (model not in models.catalog() or not models.installed(model)):
            raise CyToolError('MissingModel',
                              'The translation model "%s" is not installed; install it in Models '
                              'or choose another one.' % model)
        return {'llm_model': model or _assistant_model(persona),
                'device': _assistant_device(parameters, persona),
                'temperature': parameters['temperature']
                if parameters.get('temperature') is not None else 0.2,
                'top_p': 0.9, 'repeat_penalty': 1.0,
                'seed': parameters['seed'] if parameters.get('seed') is not None else 42,
                'threads': parameters.get('threads') or 8,
                'keep_loaded': True}

    def translate(context, parameters):
        """Translate a stored scene, or a text, keeping every delivery mark in place.

        A scene's translations are written beside its turns; the original is never touched.
        Every request carries the context the words need — the world, its places and terms,
        who speaks and how, where the scene stands, and the lines just before — so that an
        ambiguous word takes the sense it has here. A text given with a session is translated
        in the light of that scene and nothing is stored.
        """
        with exclusive(context):
            target = parameters['target_language']
            persona_id = (parameters.get('persona_id') or '').strip()
            persona = library.personas.get(persona_id) if persona_id else None
            session_id = (parameters.get('session_id') or '').strip()
            free_text = str(parameters.get('text') or '')
            if session_id and not persona_id:
                raise CyToolError('InvalidParameters',
                                  'A session belongs to a stored character; give persona_id.')
            if not session_id and not free_text.strip():
                raise CyToolError('InvalidParameters',
                                  'Give a session (with its character) or a text to translate.')
            source = (parameters.get('source_language') or '').strip()
            if not source and persona:
                source = voice_delivery.native_language(persona)
            if source == target:
                raise CyToolError('InvalidParameters',
                                  'The text is already in %s. Choose another language.' % target)

            # Names are the one thing a translator must not translate.
            names, world = [], None
            if persona:
                world, _ = resolve_world(persona, parameters)
                names.append(persona.get('name', ''))
            elif (parameters.get('world_id') or '').strip() \
                    and library.worlds.exists(parameters['world_id'].strip()):
                world = library.worlds.get(parameters['world_id'].strip())
            if world:
                names.append(world.get('name', ''))
                names += [entry.get('name', '') for entry in library.cast(world.get('id', ''))
                          if world.get('id')]

            session, entries, skipped, originals, marks, speakers = None, [], [], {}, {}, {}
            if session_id:
                session = sessions.get(persona_id, session_id)
            if session is not None and not free_text.strip():
                chosen = set(parameters.get('turns') or [])
                only_character = parameters.get('roles', 'all') == 'assistant'
                for index, turn in enumerate(session.get('turns', [])):
                    if chosen and index not in chosen:
                        continue
                    if only_character and turn.get('role') != 'assistant':
                        continue
                    done = ((turn.get('translations') or {}).get(target) or {}).get('text')
                    if done and not parameters.get('overwrite'):
                        skipped.append({'turn': index, 'reason': 'already translated'})
                        continue
                    original = translation.translatable(turn)
                    masked, found = translation.protect(original)
                    if not translation.has_words(masked):
                        skipped.append({'turn': index, 'reason': 'nothing to translate'})
                        continue
                    key = 'turn_%d' % index
                    entries.append((key, masked))
                    originals[key] = (index, turn.get('role', ''), original)
                    marks[key] = found
                    speakers[key] = persona.get('name') if turn.get('role') == 'assistant' \
                        else 'the player'
            else:
                masked, found = translation.protect(free_text)
                entries.append(('text', masked))
                originals['text'] = (None, '', free_text)
                marks['text'] = found

            settings = _translation_settings(persona, parameters)
            results, seconds = [], 0.0
            groups = list(translation.batches(entries, translation.BATCH_CHARACTERS))
            speaker_names = {'assistant': (persona or {}).get('name', 'the character'),
                             'user': 'the player'}
            produced = {}

            # The terms of the world read the same in every translation: rendered once per
            # language, recorded in the world, required in every request after that.
            known_terms = translation.world_terms(world) if world else []
            lexicon = dict(((world or {}).get('term_translations') or {}).get(target) or {})
            learned, rejected = [], []
            new_terms = [item for item in translation.mentioned_terms(
                known_terms, ' '.join(text for _, text in entries))
                if not (lexicon.get(item['term']) or {}).get('text')]
            if new_terms:
                context.progress(3, currentStep='Rendering the terms of the world')
                answer = _run_model(
                    context, {**settings, 'response_length': 80 + 40 * len(new_terms)},
                    translation.terms_messages(new_terms, target=target, source=source,
                                               world=world),
                    json_schema=translation.terms_schema(new_terms), progress=(3, 5))
                stamp = library.now()
                rendered, rejected = translation.parse_terms(answer['text'], new_terms)
                for term, text in rendered.items():
                    lexicon[term] = {'text': text, 'source': 'model',
                                     'model': settings['llm_model'], 'at': stamp}
                    learned.append(term)
                if learned and parameters.get('keep_terms', True) and world.get('id') \
                        and library.worlds.exists(world['id']):
                    stored = library.worlds.get(world['id'])
                    table = dict(stored.get('term_translations') or {})
                    language_table = dict(table.get(target) or {})
                    for term in learned:
                        # A rendering written by the person is never replaced.
                        if (language_table.get(term) or {}).get('source') != 'person':
                            language_table[term] = lexicon[term]
                    table[target] = language_table
                    stored['term_translations'] = table
                    library.worlds.save(stored)
                    lexicon.update(language_table)
            renderings = {term: entry['text'] for term, entry in lexicon.items()
                          if (entry or {}).get('text')}
            # A name the lexicon renders is no longer kept as it is written: « Les Archives
            # Flottantes » becomes what the lexicon says, not French in an English sentence.
            rendered_names = {translation.fold(term) for term in renderings}
            names = [name for name in names
                     if translation.fold(str(name).split(' — ')[0]) not in rendered_names]
            terms_used, retried = {}, 0

            def required_terms(text):
                # Only the terms this text uses as names: « il faut nommer les morts » keeps
                # its verb, and is not told that « Nommer » is « the Naming ».
                return {item['term']: renderings[item['term']]
                        for item in translation.mentioned_terms(known_terms, text)
                        if item['term'] in renderings
                        and translation.used_as_name(item['term'], text)}

            def earlier_for(batch):
                """The lines just before this batch, from the scene being translated."""
                if session is None:
                    return []
                turns = session.get('turns', [])
                first = originals[batch[0][0]][0]
                before = first if first is not None else len(turns)
                return translation.earlier_lines(turns, before, target,
                                                 speaker_names=speaker_names, produced=produced)

            try:
                for number, batch in enumerate(groups):
                    low = 5 + 90.0 * number / len(groups)
                    high = 5 + 90.0 * (number + 1) / len(groups)
                    context.progress(low, currentStep='Translating %d/%d' % (number + 1, len(groups)))
                    size = sum(len(text) for _, text in batch)
                    previous = [item['text'][:300] for item in results[-translation.CONTEXT_TURNS:]]
                    focus = ' '.join(text for _, text in batch)
                    scene_context = translation.context_block(
                        world, persona, session, parameters.get('context', ''), focus)
                    answer = _run_model(
                        context, {**settings, 'response_length': min(6000, 300 + size)},
                        translation.messages(batch, target=target, source=source, names=names,
                                             speakers=speakers, previous=previous,
                                             context=scene_context,
                                             earlier=earlier_for(batch),
                                             terms=required_terms(focus)),
                        json_schema=translation.batch_schema(batch), progress=(low, high))
                    if answer.get('truncated'):
                        raise CyToolError(
                            'ResponseTruncated',
                            'The translation was cut off before its end. Translate fewer lines '
                            'at a time, or use a model with a longer context.')
                    seconds += float(answer.get('seconds', 0.0))
                    parsed = translation.parse(answer['text'], batch)
                    sources = dict(batch)
                    missing = {key: translation.missed_terms(sources[key], parsed[key],
                                                             required_terms(sources[key]))
                               for key, _ in batch}
                    again = [(key, sources[key]) for key, _ in batch if missing[key]]
                    if again:
                        retried += len(again)
                        insist = {term: renderings[term] for key, _ in again
                                  for term in missing[key]}
                        second = _run_model(
                            context, {**settings,
                                      'response_length': min(6000, 300 + sum(
                                          len(text) for _, text in again))},
                            translation.messages(again, target=target, source=source,
                                                 names=names, speakers=speakers,
                                                 context=scene_context,
                                                 earlier=earlier_for(again),
                                                 terms=required_terms(
                                                     ' '.join(text for _, text in again)),
                                                 insist=insist),
                            json_schema=translation.batch_schema(again), progress=(high, high))
                        seconds += float(second.get('seconds', 0.0))
                        redone = translation.parse(second['text'], again)
                        for key, _ in again:
                            left = translation.missed_terms(sources[key], redone[key],
                                                            required_terms(sources[key]))
                            if len(left) < len(missing[key]):
                                parsed[key], missing[key] = redone[key], left
                    for key, _ in batch:
                        terms_used.update(required_terms(sources[key]))
                        text, lost = translation.restore(parsed[key], marks[key])
                        index, role, original = originals[key]
                        results.append({'turn': index, 'role': role, 'original': original,
                                        'text': text, 'marksLost': lost,
                                        'termsMissed': ['%s → %s' % (term, renderings[term])
                                                        for term in missing[key]]})
                        if index is not None:
                            produced[index] = text
            finally:
                if not parameters.get('keep_loaded'):
                    resident.stop()

            saved = False
            if session is not None and not free_text.strip() and results \
                    and parameters.get('save', True):
                stamp = library.now()
                for item in results:
                    turn = session['turns'][item['turn']]
                    stored = dict((turn.get('translations') or {}).get(target) or {})
                    if stored.get('text') != item['text']:
                        stored.pop('audio', None)       # a take of the old words no longer fits
                    stored.update(text=item['text'], model=settings['llm_model'], at=stamp,
                                  marksLost=item['marksLost'], termsMissed=item['termsMissed'])
                    turn.setdefault('translations', {})[target] = stored
                sessions.save(session)
                saved = True

            outputs = {'language': target, 'source': source or 'Auto',
                       'model': settings['llm_model'], 'device': settings['device'],
                       'translations': results, 'skipped': skipped, 'seconds': round(seconds, 2),
                       'saved': saved, 'sessionId': session_id,
                       'text': results[0]['text'] if free_text.strip() and results else '',
                       'context': bool(world or persona or session
                                       or (parameters.get('context') or '').strip()),
                       'marksLost': sum(len(item['marksLost']) for item in results),
                       'worldId': (world or {}).get('id', ''), 'terms': terms_used,
                       'termsLearned': learned, 'termsRejected': rejected,
                       'termsRetried': retried,
                       'termsMissed': sum(len(item['termsMissed']) for item in results)}
            path = context.path('outputs/translation.json')
            write_json(path, outputs)
            outputs['file'] = str(path)
            context.progress(100, currentStep='Translation ready')
            return outputs

    def translation_terms(context, parameters):
        """The places, factions and terms of a world, with how each is rendered in a language."""
        world = library.worlds.get(parameters['world_id'])
        language = parameters['language']
        table = ((world.get('term_translations') or {}).get(language) or {})
        return {'worldId': world['id'], 'language': language, 'terms': [
            {**item, 'text': (table.get(item['term']) or {}).get('text', ''),
             'source': (table.get(item['term']) or {}).get('source', ''),
             'model': (table.get(item['term']) or {}).get('model', '')}
            for item in translation.world_terms(world)]}

    def set_term_translations(context, parameters):
        """Fix how terms are rendered in a language. Yours are never replaced by the model;
        an empty text forgets the rendering, so the next translation renders it again."""
        world = library.worlds.get(parameters['world_id'])
        language = parameters['language']
        table = dict(world.get('term_translations') or {})
        language_table = dict(table.get(language) or {})
        changed = []
        for item in parameters.get('terms') or []:
            term = str(item.get('term') or '').strip()
            text = ' '.join(str(item.get('text') or '').split())
            if not term:
                continue
            if text:
                language_table[term] = {'text': text, 'source': 'person', 'model': '',
                                        'at': library.now()}
            else:
                language_table.pop(term, None)
            changed.append(term)
        table[language] = language_table
        world['term_translations'] = table
        saved = library.worlds.save(world)
        return {'worldId': world['id'], 'language': language, 'changed': changed,
                'revision': saved.get('revision', 0)}

    # ------------------------------------------------------------------- batches

    def _batch_speaker(line, cast, task, voices):
        """Who speaks a line of a batch: (persona, 'task' | 'library' | 'voice', reason).

        The character found when the batch was created is kept, so a resumed batch speaks
        with the same one; a line whose character was missing is looked up again. `voices`
        maps the stable voices this task may use to their names.
        """
        persona, origin, reason = None, '', ''
        identifier, source = line.get('speakerId'), line.get('speakerSource')
        if identifier and source == 'task' and identifier in task['sheets']:
            persona, origin = task['sheets'][identifier], 'task'
        elif identifier and source == 'library' and cast.use_library \
                and library.personas.exists(identifier):
            persona, origin = library.personas.get(identifier), 'library'
        elif line.get('character'):
            persona, origin, reason = cast.locate(line['character'])
        if line.get('voice'):
            if line['voice'] not in voices:
                return None, '', 'No stable voice called "%s".' % line['voice']
            # A voice alone speaks under its own name, with no character sheet behind it.
            base = persona or {**normalize_persona({}), 'id': '', 'name': voices[line['voice']]}
            return ({**base, 'voice': {**base['voice'], 'voice_id': line['voice']}},
                    origin if persona else 'voice', '')
        if persona is None and not reason:
            reason = 'The line names neither a character nor a voice.'
        return persona, origin, reason

    def _batch_world(persona, origin, task, use_library):
        world_id = persona.get('world_id') or ''
        if origin == 'task' and world_id in task['worlds']:
            return task['worlds'][world_id]
        if use_library and world_id and library.worlds.exists(world_id):
            return library.worlds.get(world_id)
        return None

    def speak_batch(context, parameters):
        """Speak a list of lines, as many at a time as the free VRAM allows, into one folder.

        Lines already written by an earlier run of the same batch are not generated again.
        A line that cannot be spoken is reported and the rest of the batch goes on.
        dry_run only reads the list and says who would speak each line, with which voice:
        nothing is generated and no folder is made, so it needs neither the GPU nor the lock.
        """
        if parameters.get('dry_run'):
            return _speak_batch(context, parameters, dry_run=True)
        with exclusive(context):
            return _speak_batch(context, parameters)

    def _speak_batch(context, parameters, dry_run=False):
        device = parameters.get('device', 'cuda')
        default_language = (parameters.get('language') or '').strip()
        lines = None
        if parameters.get('resume'):
            folder = batches.folder_of(parameters['resume'])
            document = read_json(folder / 'lot.json')
            lines = document['lines']
            use_library = bool(document.get('useLibrary', True))
            previous = {line['index']: line for line in
                        (read_json(folder / 'resultats.json') or {}).get('lines', [])}
        else:
            source = (parameters.get('file') or '').strip()
            written = parameters.get('format', 'auto')
            if written == 'auto' and (parameters.get('text') or '').strip():
                written = batches.guess_format(parameters['text'])
            parsed = batches.parse(source, parameters.get('text', ''), parameters.get('items'),
                                   written)
            name = (parameters.get('name') or '').strip() or (Path(source).stem if source
                                                              else 'lot')
            use_library = bool(parameters.get('use_library', True))
            previous = {}
            # A check imports the task's characters into its own job workspace, a real
            # batch into its folder: either way the library is never written.
            folder = context.workspace / 'task' if dry_run else batches.create_folder(name)
            if parameters.get('personas'):
                context.progress(0, currentStep='Importing the characters of the task')
                try:
                    batches.import_task_personas(folder, parameters['personas'])
                except Exception:
                    if not dry_run:                 # the folder was made a moment ago, empty
                        shutil.rmtree(folder, ignore_errors=True)
                    raise
        task = batches.load_task(folder)
        cast = batches.Cast(task['sheets'].values(), use_library)
        voices = {voice['id']: voice.get('name') or voice['id']
                  for voice in (voice_stable.listing() if use_library else [])}
        voices.update({identifier: document.get('name') or identifier
                       for identifier, document in task['voices'].items()})

        if lines is None:
            duplicates = batches.assign_ids(parsed)
            lines, used = [], set()
            for index, line in enumerate(parsed, 1):
                persona, origin, _ = _batch_speaker(line, cast, task, voices)
                entry = {'index': index, **line,
                         'language': line.get('language') or default_language,
                         'speakerId': (persona or {}).get('id', ''),
                         'speakerSource': origin if persona else '',
                         'speakerName': (persona or {}).get('name', '')}
                if index - 1 in duplicates:
                    entry['duplicate'] = duplicates[index - 1]
                entry['file'] = batches.file_stem(index, entry, used)
                lines.append(entry)
            document = {'format': 'cytools-personarp-batch', 'name': name,
                        'created': library.now(), 'device': device,
                        'language': default_language, 'useLibrary': use_library,
                        'personas': [{'id': sheet['id'], 'name': sheet['name'],
                                      'voices': library.voice_ids(sheet)}
                                     for sheet in task['sheets'].values()],
                        'lines': lines}
            if not dry_run:
                if parameters.get('items'):
                    write_json(folder / 'source.json', parameters['items'])
                elif source:
                    shutil.copyfile(source, folder / ('source' + Path(source).suffix.lower()))
                else:
                    extension = {'json': '.json', 'csv': '.csv'}.get(written, '.txt')
                    (folder / ('source' + extension)).write_text(parameters['text'],
                                                                 encoding='utf-8')
                write_json(folder / 'lot.json', document)

        context.progress(1, currentStep='Reading the batch')
        # What is left to do, grouped by the weights that will speak it.
        results, groups, skipped = [], {}, 0
        for position, line in enumerate(lines):
            earlier = previous.get(line['index']) or {}
            if earlier.get('status') == 'ok' and earlier.get('file') \
                    and (folder / earlier['file']).is_file():
                results.append(earlier)
                skipped += 1
                continue
            entry = {**line, 'file': 'voix/' + line['file'] + '.wav', 'status': 'error',
                     'error': ''}
            results.append(entry)
            if line.get('duplicate'):
                entry['error'] = line['duplicate']
                continue
            persona, origin, reason = _batch_speaker(line, cast, task, voices)
            if persona is None:
                entry['error'] = reason
                continue
            entry.update(speakerId=persona.get('id', ''), speakerSource=origin,
                         speakerName=persona.get('name', ''))
            voice = persona['voice']
            spoken = scene.spoken_text(line['text'],
                                       keep_annotations=bool(voice.get('annotations')),
                                       speak_narration=bool(voice.get('speak_narration')))
            if not spoken.strip():
                entry['error'] = 'Nothing to say once the stage directions are left out.'
                continue
            try:
                payload, note = voice_delivery.payload_for(
                    persona, spoken, world=_batch_world(persona, origin, task, use_library),
                    device=device, language=line.get('language', ''), voices=task['voices'])
            except CyToolError as exc:
                entry['error'] = str(exc)
                continue
            plan = payload.get('voice_plan', {})
            entry.update(status='pending', note=note, mode=payload['mode'],
                         model=payload['model'], languageUsed=payload['language'],
                         voiceUsed=plan.get('voice_id') or plan.get('speaker') or '')
            groups.setdefault((payload['mode'], payload['model'], payload['model_path']),
                              []).append((position, {
                                  'id': str(position), 'file': line['file'],
                                  'text': payload['text'], 'language': payload['language'],
                                  'instruction': payload['instruction'],
                                  'speaker': payload.get('speaker', ''),
                                  'reference_audio': payload.get('reference_audio', ''),
                                  'reference_text': payload.get('reference_text', ''),
                                  'x_vector_only': bool(payload.get('x_vector_only')),
                                  'annotations': payload['annotations'],
                                  'delivery': payload['delivery']}))
        personas = [{'id': sheet['id'], 'name': sheet['name']} for sheet in task['sheets'].values()]
        if dry_run:
            ready = [line for line in results if line['status'] == 'pending']
            return {'dryRun': True, 'batch': folder.name if parameters.get('resume') else '',
                    'lines': len(lines), 'ready': len(ready), 'skipped': skipped,
                    'failed': sum(1 for line in results if line['status'] == 'error'),
                    'personas': personas, 'problems': task['problems'],
                    'groups': [{'mode': mode, 'model': model_id, 'lines': len(members)}
                               for (mode, model_id, _), members in groups.items()],
                    'preview': [{key: line.get(key, '') for key in (
                        'index', 'id', 'status', 'character', 'voice', 'speakerName',
                        'speakerSource', 'text', 'language', 'languageUsed', 'mode', 'voiceUsed',
                        'file', 'note', 'error')} for line in results[:1000]]}
        batches.write_results(folder, results)

        statistics = []
        total = sum(len(items) for items in groups.values()) or 1
        finished = 0
        for (mode, model_id, model_path), members in groups.items():
            share = 95.0 * len(members) / total
            context.cancellation.check()
            try:
                outcome = voice_runner.speak_batch(context, {
                    'model': model_id, 'model_path': model_path, 'mode': mode,
                    'device': device, 'batch_size': int(parameters.get('batch_size') or 0),
                    'seed': int(parameters.get('seed') or 42),
                    'precision': parameters.get('precision', 'auto'),
                    'items': [item for _, item in members],
                    'workspace': str(context.workspace), 'output_dir': 'outputs/batch'},
                    offset=2.0 + 95.0 * finished / total, scale=share / 100.0)
            except CyToolError as exc:
                context.cancellation.check()      # a cancelled batch stops; a failed group does not
                for position, _ in members:
                    results[position].update(status='error', error=str(exc))
                batches.write_results(folder, results)
                finished += len(members)
                continue
            finished += len(members)
            by_id = {item['id']: item for item in outcome['items']}
            for position, item in members:
                produced = by_id.get(item['id'], {})
                if produced.get('error') or not produced.get('file'):
                    results[position].update(status='error',
                                             error=produced.get('error') or 'No take was produced.')
                    continue
                target = folder / 'voix' / (item['file'] + '.wav')
                shutil.move(produced['file'], target)
                results[position].update(status='ok',
                                         durationSeconds=round(produced['durationSeconds'], 2))
            batches.write_results(folder, results)       # progress survives an interruption
            statistics.append({key: outcome.get(key) for key in (
                'mode', 'model', 'batchSize', 'firstBatchSize', 'calls', 'memoryRetries',
                'passages', 'generationSeconds', 'vramPeakBytes', 'freeVramBytes', 'gpuName',
                'batchSizes', 'perPassageBytes', 'limitBytes', 'precision')})
        summary = batches.write_results(folder, results)
        context.progress(100, currentStep='Batch written')
        return {'batch': folder.name, 'folder': str(folder), 'lines': len(lines),
                'done': summary['done'], 'failed': summary['failed'], 'skipped': skipped,
                'results': str(folder / 'resultats.json'), 'groups': statistics,
                'personas': personas, 'problems': task['problems'],
                'errors': [{'index': line['index'], 'id': line.get('id', ''),
                            'error': line.get('error', '')}
                           for line in results if line.get('status') == 'error'][:50]}

    # ------------------------------------------------------------------ ComfyUI

    def comfyui_nodes_status(context, parameters):
        """The ComfyUIs found on this machine, the one given, and whether the nodes are in."""
        found = comfyui.candidates()
        if (parameters.get('comfyui_path') or '').strip():
            given = parameters['comfyui_path'].strip()
            if all(entry['path'] != given for entry in found):
                found.insert(0, {'path': given, 'name': 'ComfyUI', 'source': 'given', 'python': ''})
        return {'comfyui': [{**entry, **comfyui.status(entry['path'])} for entry in found],
                'nodes': comfyui.node_names(), 'packDigest': comfyui.pack_digest(),
                'toolRoot': str(ROOT)}

    def install_comfyui_nodes(context, parameters):
        return comfyui.install(parameters['comfyui_path'], port=parameters.get('port', 8791),
                               auto_start=parameters.get('auto_start', True))

    def list_batches(context, parameters):
        return {'batches': batches.listing(), 'folder': str(batches.BATCHES)}

    def speak_turn(context, parameters):
        """Speak one line of a stored scene, in its own language or in one of its translations.

        The take is kept with the scene, so a translated scene carries its audio with it.
        """
        with exclusive(context):
            persona = library.personas.get(parameters['persona_id'])
            world, _ = resolve_world(persona, parameters)
            session = sessions.get(persona['id'], parameters['session_id'])
            turns = session.get('turns', [])
            index = int(parameters['turn'])
            if not 0 <= index < len(turns):
                raise CyToolError('InvalidParameters', 'This scene has no line %d.' % index)
            turn = turns[index]
            if turn.get('role') != 'assistant':
                raise CyToolError('InvalidParameters',
                                  "Only the character's lines are spoken with its voice.")
            language = (parameters.get('language') or '').strip()
            if language:
                stored = (turn.get('translations') or {}).get(language) or {}
                if not stored.get('text'):
                    raise CyToolError('MissingInput',
                                      'This line has no %s translation yet; translate the scene '
                                      'first.' % language)
                text = stored['text']
            else:
                text = translation.translatable(turn)
            voice = persona['voice']
            spoken = scene.spoken_text(text, keep_annotations=bool(voice.get('annotations')),
                                       speak_narration=bool(voice.get('speak_narration')))
            if not spoken.strip():
                raise CyToolError('InvalidParameters',
                                  'This line has nothing to say aloud once the stage directions '
                                  'are left out.')
            user_text = ''
            if index > 0 and turns[index - 1].get('role') == 'user':
                asked = turns[index - 1]
                user_text = (((asked.get('translations') or {}).get(language) or {}).get('text')
                             if language else '') or str(asked.get('content', ''))
            result = _render_voice(context, persona, spoken, world, user_text, turn.get('scene'),
                                   overrides={**parameters, 'language': language})
            kept = result['file']
            if parameters.get('keep', True):
                folder = sessions.folder(persona['id']) / 'audio' / session['id']
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / ('turn-%03d-%s.wav' % (index, (language or 'original').lower()))
                shutil.copyfile(result['file'], target)
                kept = str(target)
                record = {'file': kept, 'durationSeconds': result.get('durationSeconds', 0.0),
                          'voice': result.get('voicePlan', {}), 'at': library.now()}
                if language:
                    turn['translations'][language]['audio'] = record
                else:
                    turn['audio'] = record
                sessions.save(session)
            context.progress(100, currentStep='Take ready')
            return {**result, 'file': kept, 'workspaceFile': result['file'], 'turn': index,
                    'text': spoken}

    # -------------------------------------------------------------------- scene

    def scene_prompts(context, parameters):
        directive = normalize_scene(parameters['scene'])
        persona = None
        if parameters.get('persona_id'):
            persona = library.personas.get(parameters['persona_id'])
        world = None
        world_id = (parameters.get('world_id') or (persona or {}).get('world_id') or '').strip()
        if world_id and library.worlds.exists(world_id):
            world = library.worlds.get(world_id)
        prompts = scene.to_prompts(directive, persona, world)
        keep = parameters.get('targets') or []
        renderings = {k: v for k, v in (directive.get('renderings') or {}).items()
                      if not keep or k in keep}
        path = context.path('outputs/scene.json')
        write_json(path, {**directive, **prompts, 'renderings': renderings})
        return {**prompts, 'renderings': renderings,
                'summary': scene.scene_summary(directive), 'file': str(path)}

    # ------------------------------------------------------------------- models

    def list_models(context, parameters):
        return {'models': models.catalog_status(bool(parameters.get('verify')), context),
                'engine': models.engine_status()}

    def maintenance_handler(handler):
        def wrapped(context, parameters):
            # Its turn first: stopping the resident model under a scene being written would
            # break that scene. The handler takes the same lock again, which a holder may.
            with exclusive(context):
                resident.stop()
                with exclusive(context, name='resident'):
                    return handler(context, parameters)
        return wrapped

    def install_llm(context, parameters):
        with exclusive(context):
            result = models.install(context, parameters)
            for backend in runtime.descriptor.get('backends', []):
                for model in backend.get('models', []):
                    model['installed'] = models.installed(model['id'])
            return result

    def install_cuda(context, parameters):
        with exclusive(context):
            return models.install_cuda(context, parameters)

    def unload_model(context, parameters):
        with exclusive(context):                # after the generation using it, not during
            resident.stop()
        return {'loaded': False}

    def diagnose_backend(context, parameters):
        verify = bool(parameters.get('verify'))
        result = {
            'models': models.catalog_status(verify, context),
            'engine': models.engine_status(),
            'resident': resident.health(),
            'platform': sys.platform,
            'library': {'personas': len(library.personas.ids()),
                        'worlds': len(library.worlds.ids()),
                        'sessions': len(sessions.listing()),
                        'voices': len(list((DATA / 'voices').glob('*.json')))
                        if (DATA / 'voices').is_dir() else 0},
            'paths': {'root': str(ROOT), 'data': str(DATA), 'runtime': str(RUNTIME),
                      'models': str(LLM_MODELS), 'exports': str(EXPORTS),
                      'freeBytes': models.disk_free()},
            'speech': {'installed': False,
                       'note': 'No speech engine in this build; chat returns voiceError.'},
        }
        path = context.path('outputs/diagnosis.json')
        write_json(path, result)
        result['file'] = str(path)
        return result

    runtime.register('chat', chat, estimate=lambda p, b, m: {
        # VRAM and the weights' RAM are reserved by the resident model as a worker;
        # declaring them here too would spend the same memory twice.
        'ramBytes': 1024 ** 3, 'cpuThreads': p.get('threads') or 4,
        'diskBytes': 256 * 1024 ** 2, 'vramBytes': {}})
    runtime.register('preview_prompt', preview_prompt)
    runtime.register('author', author, estimate=lambda p, b, m: {
        # VRAM and the weights' RAM are reserved by the resident model as a worker;
        # declaring them here too would spend the same memory twice.
        'ramBytes': 1024 ** 3, 'cpuThreads': p.get('threads') or 4, 'vramBytes': {}})
    runtime.register('apply_proposal', apply_proposal)
    runtime.register('list_personas', list_personas)
    runtime.register('get_persona', get_persona)
    runtime.register('create_persona', create_persona)
    runtime.register('save_persona', save_persona)
    runtime.register('duplicate_persona', duplicate_persona)
    runtime.register('remove_persona', remove_persona)
    runtime.register('persona_revisions', persona_revisions)
    runtime.register('restore_persona', restore_persona)
    runtime.register('list_worlds', list_worlds)
    runtime.register('get_world', get_world)
    runtime.register('create_world', create_world)
    runtime.register('save_world', save_world)
    runtime.register('remove_world', remove_world)
    runtime.register('set_relation', set_relation)
    runtime.register('drop_relation', drop_relation)
    runtime.register('remember', remember)
    runtime.register('export_personas', export_personas)
    runtime.register('import_personas', import_personas)
    runtime.register('list_examples', list_examples)
    runtime.register('list_sessions', list_sessions)
    runtime.register('get_session', get_session)
    runtime.register('new_session', new_session)
    runtime.register('remove_session', remove_session)
    runtime.register('translate', translate, estimate=lambda p, b, m: {
        # Like the other text passes: the resident model reserves its own VRAM as a worker.
        'ramBytes': 1024 ** 3, 'cpuThreads': 4, 'vramBytes': {}})
    runtime.register('speak_turn', speak_turn, estimate=lambda p, b, m: {
        'ramBytes': 8 * 1024 ** 3, 'cpuThreads': 4,
        'vramBytes': {'auto': 6 * 1024 ** 3} if p.get('device', 'cuda') == 'cuda' else {}})
    def batch_estimate(p, b, m):
        # The worker fills whatever VRAM is free; this is only what it needs to start.
        if p.get('dry_run'):
            return {'ramBytes': 256 * 1024 ** 2, 'vramBytes': {}}
        return {'ramBytes': 8 * 1024 ** 3, 'cpuThreads': 4,
                'vramBytes': {'auto': 6 * 1024 ** 3} if p.get('device', 'cuda') == 'cuda' else {}}

    # One handler. The list given inline needs no permission — it is how an AI client sends
    # its dialogues; reading a file from the disk is reserved to clients allowed to.
    runtime.register('speak_batch', speak_batch, estimate=batch_estimate)
    runtime.register('speak_batch_file', speak_batch, estimate=batch_estimate)
    runtime.register('list_batches', list_batches)
    runtime.register('translation_terms', translation_terms)
    runtime.register('set_term_translations', set_term_translations)
    runtime.register('comfyui_nodes_status', comfyui_nodes_status)
    runtime.register('install_comfyui_nodes', install_comfyui_nodes)
    runtime.register('scene_prompts', scene_prompts)
    runtime.register('assistant_chat', assistant_chat, estimate=lambda p, b, m: {
        # VRAM and the weights' RAM are reserved by the resident model as a worker;
        # declaring them here too would spend the same memory twice.
        'ramBytes': 1024 ** 3, 'cpuThreads': 8, 'vramBytes': {}})
    runtime.register('list_assistant_threads', list_assistant_threads)
    runtime.register('new_assistant_thread', new_assistant_thread)
    runtime.register('get_assistant_thread', get_assistant_thread)
    runtime.register('save_assistant_thread', save_assistant_thread)
    runtime.register('remove_assistant_thread', remove_assistant_thread)
    runtime.register('list_images', list_images)
    runtime.register('add_persona_image', add_persona_image)
    runtime.register('remove_persona_image', remove_persona_image)
    runtime.register('verify_persona_images', verify_persona_images)
    runtime.register('describe_image', describe_image, estimate=lambda p, b, m: {
        # VRAM and the weights' RAM are reserved by the resident model as a worker;
        # declaring them here too would spend the same memory twice.
        'ramBytes': 1024 ** 3, 'cpuThreads': 4, 'vramBytes': {}})
    runtime.register('speak', speak, estimate=lambda p, b, m: {
        'ramBytes': 8 * 1024 ** 3, 'cpuThreads': 4,
        'vramBytes': {'auto': 6 * 1024 ** 3} if p.get('device', 'cuda') == 'cuda' else {}})
    runtime.register('capture_voice_take', capture_voice_take, estimate=lambda p, b, m: {
        'ramBytes': 8 * 1024 ** 3, 'cpuThreads': 4,
        'vramBytes': {'auto': 6 * 1024 ** 3} if p.get('device', 'cuda') == 'cuda' else {}})
    runtime.register('create_stable_voice', create_stable_voice)
    runtime.register('list_voices', list_voices)
    runtime.register('verify_voice', verify_voice)
    runtime.register('remove_voice', remove_voice)
    runtime.register('transcribe', transcribe, estimate=lambda p, b, m: {
        'ramBytes': 6 * 1024 ** 3, 'cpuThreads': 4,
        'vramBytes': {'auto': 4 * 1024 ** 3} if p.get('device', 'cuda') == 'cuda' else {}})
    runtime.register('list_voice_models', list_voice_models)
    runtime.register('install_voice_model', install_voice_model,
                     estimate=lambda p, b, m: voice_catalog.installation_resources(p['model']))
    runtime.register('install_voice_engine', install_voice_engine,
                     estimate=lambda p, b, m: {'diskBytes': 9 * 1024 ** 3, 'cpuThreads': 2})
    runtime.register('release_voice', release_voice)
    runtime.register('list_models', list_models)
    runtime.register('install_llm', maintenance_handler(install_llm),
                     estimate=lambda p, b, m: models.installation_resources(p['model']))
    runtime.register('install_cuda', maintenance_handler(install_cuda))
    runtime.register('unload_model', unload_model)
    runtime.register('diagnose_backend', diagnose_backend)
    runtime.register('update', maintenance_handler(maintenance.update))

    from cytools_core.shared_installation import register_operations
    register_operations(runtime, ROOT)
    return runtime


if __name__ == '__main__':
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    argv = sys.argv[1:]
    if '--data-dir' not in argv:
        argv = ['--data-dir', str(DATA / 'jobs'), *argv]
    raise SystemExit(run_cli(create_runtime, argv))
