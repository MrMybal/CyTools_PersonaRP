"""The PersonaRP nodes: characters, dialogue, voice, scene prompts, translation, photographs,
voice tasks, and any operation of the Tool.

Every node submits an operation to CyTools PersonaRP through its local API (client.py) and
follows it with ComfyUI's progress bar; ComfyUI's Stop button cancels the job in the Tool.
Before a job that needs the graphics card, the models ComfyUI holds can be unloaded, and
after it the Tool can give its own memory back — both on by default, because a 24 GB card
does not hold an image model, a language model and a voice model at once.
"""
import json
import os
import shutil
import time
import wave
from pathlib import Path

from .client import CLIENT, ToolError, tool_root

CATEGORY = 'CyTools/PersonaRP'
OWN_LANGUAGE = '(sa propre langue)'
SHEET = '(celui de la fiche)'
NONE = '(aucun)'
LIST_TTL = 20.0
_cache = {}


# ----------------------------------------------------------------------- helpers

def _comfy():
    """ComfyUI's modules when running inside it; None when imported elsewhere (tests)."""
    try:
        import comfy.model_management as management
        import comfy.utils as utils
        import folder_paths
        return management, utils, folder_paths
    except ImportError:
        return None, None, None


def _listing(key, live, offline, fallback):
    """A dropdown's values, cached a few seconds (ComfyUI asks often).

    From the Tool when its server is already running; otherwise read from its files, so that
    opening ComfyUI never starts PersonaRP — only running one of its nodes does.
    """
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < LIST_TTL:
        return cached[1]
    values = None
    for loader in ((live, offline) if CLIENT.running() else (offline,)):
        try:
            values = loader()
        except Exception:                                      # noqa: BLE001 - a menu must load
            values = None
        if values:
            break
    values = values or fallback
    _cache[key] = (now, values)
    return values


def _documents(folder):
    """The JSON documents of a folder of the Tool's library (read only)."""
    documents = []
    for path in sorted((tool_root() / 'data' / folder).glob('*.json')):
        try:
            documents.append(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            continue
    return documents


def _catalog(name):
    try:
        return json.loads((tool_root() / 'app' / name).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}


def _descriptor():
    try:
        return json.loads((tool_root() / 'app' / 'CyTool.json').read_text(encoding='utf-8'))
    except Exception:                                          # noqa: BLE001
        return {'operations': []}


def _operation(name):
    return next((op for op in _descriptor()['operations'] if op['id'] == name), {})


def languages():
    enum = _operation('speak').get('inputSchema', {}).get('properties', {}) \
        .get('language', {}).get('enum') or []
    return [value for value in enum if value] or ['French', 'English']


def _labels(entries):
    return sorted('%s [%s]' % (entry.get('name') or entry['id'], entry['id'])
                  for entry in entries if entry.get('id'))


def characters():
    return _listing('characters',
                    lambda: _labels(CLIENT.run('list_personas', {})['personas']),
                    lambda: _labels(_documents('personas')),
                    ['(aucun personnage — PersonaRP introuvable)'])


def voices():
    return _listing('voices',
                    lambda: [NONE] + _labels(CLIENT.run('list_voices', {})['voices']),
                    lambda: [NONE] + _labels(_documents('voices')), [NONE])


def llm_models():
    # Offline, the whole catalogue: whether a model is installed is the Tool's to say, and it
    # says so clearly when a node asks for one that is not.
    return _listing('llm',
                    lambda: [SHEET] + [entry['id'] for entry in CLIENT.run(
                        'list_models', {'verify': False})['models'] if entry.get('installed')],
                    lambda: [SHEET] + sorted(_catalog('llm-catalog.json')), [SHEET])


def vision_models():
    return _listing('vision',
                    lambda: [SHEET] + [entry['id'] for entry in CLIENT.run(
                        'list_models', {'verify': False})['models']
                        if entry.get('installed') and entry.get('vision')],
                    lambda: [SHEET] + sorted(key for key, info in _catalog('llm-catalog.json')
                                             .items() if isinstance(info, dict)
                                             and info.get('vision')),
                    [SHEET])


def operations():
    return sorted(op['id'] for op in _descriptor()['operations']) or ['list_personas']


def identifier(label):
    """'Maëlis de Corvanne [maelis-de-corvanne]' -> 'maelis-de-corvanne'."""
    label = (label or '').strip()
    if label.endswith(']') and '[' in label:
        return label.rsplit('[', 1)[1][:-1]
    return '' if label.startswith('(') else label


def persona_of(choice, override=''):
    return (override or '').strip() or identifier(choice)


def free_comfyui_memory(enabled):
    management, _, _ = _comfy()
    if enabled and management is not None:
        management.unload_all_models()
        management.soft_empty_cache()


def give_back(enabled, *operations_):
    """Ask the Tool to release what it keeps resident (voice worker, language model)."""
    if not enabled:
        return
    for name in operations_:
        try:
            CLIENT.run(name, {})
        except ToolError:
            pass


def run(operation, parameters):
    """Run an operation with ComfyUI's progress bar and Stop button."""
    management, utils, _ = _comfy()
    bar = utils.ProgressBar(100) if utils is not None else None

    def progress(percent, step):
        if bar is not None:
            bar.update_absolute(int(max(0, min(100, percent))), 100)

    def interrupted():
        return bool(management is not None and management.processing_interrupted())

    try:
        return CLIENT.run(operation, parameters, progress, interrupted)
    except ToolError as exc:
        if exc.code == 'Cancelled' and management is not None:
            management.throw_exception_if_processing_interrupted()
        raise RuntimeError('PersonaRP — %s' % exc) from exc


def audio_from_wav(path):
    """A WAV file as ComfyUI's AUDIO: {'waveform': [1, channels, samples], 'sample_rate'}."""
    import numpy
    import torch
    with wave.open(str(path), 'rb') as handle:
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    kinds = {1: (numpy.uint8, 128.0, 128.0), 2: (numpy.int16, 0.0, 32768.0),
             4: (numpy.int32, 0.0, 2147483648.0)}
    kind, offset, scale = kinds.get(width, kinds[2])
    samples = (numpy.frombuffer(frames, dtype=kind).astype(numpy.float32) - offset) / scale
    samples = samples.reshape(-1, channels).T.copy()
    return {'waveform': torch.from_numpy(samples).unsqueeze(0), 'sample_rate': int(rate)}


def silence(seconds=0.1, rate=24000):
    import torch
    return {'waveform': torch.zeros(1, 1, max(1, int(seconds * rate))), 'sample_rate': rate}


def join_audio(paths, gap=0.4):
    """Several takes one after the other, with a short silence between them."""
    import torch
    pieces, rate = [], None
    for path in paths:
        audio = audio_from_wav(path)
        rate = rate or audio['sample_rate']
        if audio['sample_rate'] != rate:
            continue
        pieces.append(audio['waveform'].mean(dim=1, keepdim=True))
        pieces.append(torch.zeros(1, 1, int(gap * rate)))
    if not pieces:
        return silence()
    return {'waveform': torch.cat(pieces[:-1], dim=2), 'sample_rate': rate}


def keep_file(path, name):
    """A copy of a take in ComfyUI's output folder, so it outlives the Tool's job."""
    _, _, folder_paths = _comfy()
    if folder_paths is None or not path:
        return path
    target = Path(folder_paths.get_output_directory()) / 'personarp'
    target.mkdir(parents=True, exist_ok=True)
    destination = target / ('%s-%s%s' % (name, time.strftime('%Y%m%d-%H%M%S'), Path(path).suffix))
    shutil.copyfile(path, destination)
    return str(destination)


def image_to_file(image):
    """The first image of a ComfyUI IMAGE batch, written as a PNG the Tool can read."""
    import numpy
    from PIL import Image
    _, _, folder_paths = _comfy()
    folder = Path(folder_paths.get_temp_directory()) if folder_paths is not None \
        else Path(os.environ.get('TEMP', '/tmp'))
    folder.mkdir(parents=True, exist_ok=True)
    array = (image[0].cpu().numpy() * 255.0).clip(0, 255).astype(numpy.uint8)
    path = folder / ('personarp-%d.png' % int(time.time() * 1000))
    Image.fromarray(array).save(path)
    return str(path)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def _always_again(seed=-1, **_):
    # A seed of -1 asks for a new take every time; ComfyUI would otherwise reuse the last one.
    return float('nan') if int(seed) < 0 else ''


# ------------------------------------------------------------------------- nodes

class Character:
    """A character of PersonaRP, and what an image model needs to draw it."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'personnage': (characters(),)}}

    RETURN_TYPES = ('STRING', 'STRING', 'STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('persona_id', 'nom', 'apparence', 'etiquettes_visuelles', 'fiche_json')
    FUNCTION = 'read'
    CATEGORY = CATEGORY

    def read(self, personnage):
        outputs = run('get_persona', {'persona_id': identifier(personnage)})
        sheet = outputs['persona']
        appearance = sheet.get('appearance') or {}
        tags = ', '.join(appearance.get('visual_tags') or [])
        return (sheet['id'], sheet.get('name', ''), appearance.get('summary', ''), tags,
                dumps(sheet))


class Dialogue:
    """The character answers, in character — and describes the shot for image and video."""

    SESSIONS = ['nouvelle scène', 'continuer la dernière scène', 'continuer la scène donnée',
                'sans mémoire']

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'personnage': (characters(),),
            'message': ('STRING', {'multiline': True, 'default': 'Bonjour.'}),
            'scene': (cls.SESSIONS,),
            'directive_de_scene': (['selon la fiche', 'oui', 'non'],),
            'parler': (['selon la fiche', 'oui', 'non'],),
            'modele': (llm_models(),),
            'appareil': (['selon la fiche', 'cuda', 'cpu'],),
            'seed': ('INT', {'default': -1, 'min': -1, 'max': 2 ** 31 - 1}),
            'liberer_vram_comfyui': ('BOOLEAN', {'default': True}),
            'rendre_la_vram_apres': ('BOOLEAN', {'default': True}),
        }, 'optional': {
            'persona_id': ('STRING', {'forceInput': True}),
            'session_id': ('STRING', {'forceInput': True}),
        }}

    RETURN_TYPES = ('STRING', 'STRING', 'STRING', 'STRING', 'STRING', 'STRING', 'AUDIO', 'STRING')
    RETURN_NAMES = ('reponse', 'texte_parle', 'prompt_image', 'prompt_video', 'prompt_negatif',
                    'directive_json', 'audio', 'session_id')
    FUNCTION = 'talk'
    CATEGORY = CATEGORY

    @classmethod
    def IS_CHANGED(cls, **inputs):
        return _always_again(**inputs)

    def talk(self, personnage, message, scene, directive_de_scene, parler, modele, appareil, seed,
             liberer_vram_comfyui, rendre_la_vram_apres, persona_id='', session_id=''):
        persona = persona_of(personnage, persona_id)
        parameters = {'persona_id': persona, 'text': message, 'seed': int(seed),
                      'want_scene': {'oui': 'yes', 'non': 'no'}.get(directive_de_scene, 'auto'),
                      'speak': {'oui': 'yes', 'non': 'no'}.get(parler, 'auto')}
        if modele != SHEET:
            parameters['llm_model'] = modele
        if appareil in ('cuda', 'cpu'):
            parameters['device'] = appareil
        if scene == 'nouvelle scène':
            parameters['session_id'] = run('new_session', {'persona_id': persona})['id']
        elif scene == 'continuer la dernière scène':
            listed = run('list_sessions', {'persona_id': persona})['sessions']
            parameters['session_id'] = listed[0]['id'] if listed else \
                run('new_session', {'persona_id': persona})['id']
        elif scene == 'continuer la scène donnée':
            if not (session_id or '').strip():
                raise RuntimeError('PersonaRP — relie une session_id pour continuer une scène donnée.')
            parameters['session_id'] = session_id.strip()
        else:
            parameters['save'] = False
        free_comfyui_memory(liberer_vram_comfyui)
        try:
            outputs = run('chat', parameters)
        finally:
            give_back(rendre_la_vram_apres, 'unload_model', 'release_voice')
        prompts = outputs.get('prompts') or {}
        audio = silence()
        if outputs.get('audioFile'):
            audio = audio_from_wav(keep_file(outputs['audioFile'], persona))
        return (outputs.get('dialogue', ''), outputs.get('spoken', ''),
                prompts.get('image_prompt', ''), prompts.get('video_prompt', ''),
                prompts.get('negative_prompt', ''), dumps(outputs.get('scene') or {}), audio,
                outputs.get('sessionId') or parameters.get('session_id', ''))


class Voice:
    """A text said with a character's voice, in its language or in another."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'personnage': (characters(),),
            'texte': ('STRING', {'multiline': True, 'default': 'Bonjour.'}),
            'langue': ([OWN_LANGUAGE] + languages(),),
            'voix': (voices(),),
            'seed': ('INT', {'default': -1, 'min': -1, 'max': 2 ** 31 - 1}),
            'appareil': (['cuda', 'cpu'],),
            'liberer_vram_comfyui': ('BOOLEAN', {'default': True}),
            'rendre_la_vram_apres': ('BOOLEAN', {'default': True}),
        }, 'optional': {'persona_id': ('STRING', {'forceInput': True})}}

    RETURN_TYPES = ('AUDIO', 'STRING', 'FLOAT', 'STRING')
    RETURN_NAMES = ('audio', 'fichier', 'duree', 'voix_utilisee')
    FUNCTION = 'speak'
    CATEGORY = CATEGORY

    @classmethod
    def IS_CHANGED(cls, **inputs):
        return _always_again(**inputs)

    def speak(self, personnage, texte, langue, voix, seed, appareil, liberer_vram_comfyui,
              rendre_la_vram_apres, persona_id=''):
        persona = persona_of(personnage, persona_id)
        parameters = {'text': texte, 'device': appareil,
                      'language': '' if langue == OWN_LANGUAGE else langue}
        if persona:
            parameters['persona_id'] = persona
        if identifier(voix):
            parameters['voice_id'] = identifier(voix)
        if int(seed) >= 0:
            parameters['seed'] = int(seed)
        free_comfyui_memory(liberer_vram_comfyui)
        try:
            outputs = run('speak', parameters)
        finally:
            give_back(rendre_la_vram_apres, 'release_voice')
        kept = keep_file(outputs['file'], persona or 'voix')
        plan = outputs.get('voicePlan') or {}
        return (audio_from_wav(kept), kept, float(outputs.get('durationSeconds') or 0.0),
                plan.get('voice_id') or plan.get('speaker') or outputs.get('mode', ''))


class ScenePrompts:
    """Image and video prompts from a scene directive (the directive_json of Dialogue)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'directive_json': ('STRING', {'forceInput': True}),
            'personnage': (characters(),),
        }, 'optional': {'persona_id': ('STRING', {'forceInput': True})}}

    RETURN_TYPES = ('STRING', 'STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('prompt_image', 'prompt_video', 'prompt_negatif', 'resume')
    FUNCTION = 'build'
    CATEGORY = CATEGORY

    def build(self, directive_json, personnage, persona_id=''):
        try:
            directive = json.loads(directive_json or '{}')
        except ValueError as exc:
            raise RuntimeError('PersonaRP — directive_json illisible : %s' % exc) from exc
        if not directive:
            raise RuntimeError('PersonaRP — la directive de scène est vide.')
        outputs = run('scene_prompts', {'scene': directive,
                                        'persona_id': persona_of(personnage, persona_id)})
        return (outputs.get('image_prompt', ''), outputs.get('video_prompt', ''),
                outputs.get('negative_prompt', ''), outputs.get('summary', ''))


class Translate:
    """A text translated by a language model, delivery marks kept in place."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'texte': ('STRING', {'multiline': True, 'default': ''}),
            'vers': (languages(),),
            'depuis': (['(détecter)'] + languages(),),
            'modele': (llm_models(),),
            'personnage': ([NONE] + characters(),),
            'contexte': ('STRING', {'multiline': True, 'default': ''}),
            'liberer_vram_comfyui': ('BOOLEAN', {'default': True}),
            'rendre_la_vram_apres': ('BOOLEAN', {'default': True}),
        }, 'optional': {
            'persona_id': ('STRING', {'forceInput': True}),
            'session_id': ('STRING', {'forceInput': True}),
        }}

    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('traduction', 'modele_utilise')
    FUNCTION = 'translate'
    CATEGORY = CATEGORY

    def translate(self, texte, vers, depuis, modele, liberer_vram_comfyui, rendre_la_vram_apres,
                  personnage=NONE, contexte='', persona_id='', session_id=''):
        # The character gives its world, its way of speaking and its scene as context; a
        # session adds the lines just before. Nothing is stored.
        parameters = {'text': texte, 'target_language': vers, 'save': False,
                      'context': contexte or ''}
        persona = persona_of(personnage, persona_id)
        if persona:
            parameters['persona_id'] = persona
            if (session_id or '').strip():
                parameters['session_id'] = session_id.strip()
        if depuis in languages():
            parameters['source_language'] = depuis
        if modele != SHEET:
            parameters['llm_model'] = modele
        free_comfyui_memory(liberer_vram_comfyui)
        try:
            outputs = run('translate', parameters)
        finally:
            give_back(rendre_la_vram_apres, 'unload_model')
        return (outputs.get('text', ''), outputs.get('model', ''))


class ReadPhoto:
    """What a photograph shows of a person, written the way a character sheet wants it."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'image': ('IMAGE',),
            'langue': (['French', 'English'] + [l for l in languages()
                                                if l not in ('French', 'English')],),
            'modele': (vision_models(),),
            'liberer_vram_comfyui': ('BOOLEAN', {'default': True}),
            'rendre_la_vram_apres': ('BOOLEAN', {'default': True}),
        }}

    RETURN_TYPES = ('STRING', 'STRING', 'STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('apparence', 'etiquettes_visuelles', 'proposition_json', 'modele_utilise',
                    'observation')
    FUNCTION = 'read'
    CATEGORY = CATEGORY

    def read(self, image, langue, modele, liberer_vram_comfyui, rendre_la_vram_apres):
        parameters = {'image': image_to_file(image), 'language': langue}
        if modele != SHEET:
            parameters['llm_model'] = modele
        free_comfyui_memory(liberer_vram_comfyui)
        try:
            outputs = run('describe_image', parameters)
        finally:
            give_back(rendre_la_vram_apres, 'unload_model')
        proposal = outputs.get('proposal') or {}
        appearance = proposal.get('appearance') or proposal
        tags = ', '.join(appearance.get('visual_tags') or []) if isinstance(appearance, dict) else ''
        return (outputs.get('text', '') or (appearance.get('summary', '')
                                            if isinstance(appearance, dict) else ''),
                tags, dumps(proposal), outputs.get('model', ''), outputs.get('observation', ''))


class VoiceTask:
    """A list of lines spoken many at a time, into a task folder of PersonaRP."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'liste': ('STRING', {'multiline': True,
                                 'default': 'L-01 | Maëlis: Le col est fermé depuis trois jours.'}),
            'nom': ('STRING', {'default': 'comfyui'}),
            'langue': ([OWN_LANGUAGE] + languages(),),
            'taille_lot': ('INT', {'default': 0, 'min': 0, 'max': 64}),
            'precision': (['auto', 'bfloat16', 'float16', 'float32'],),
            'verifier_seulement': ('BOOLEAN', {'default': False}),
            'liberer_vram_comfyui': ('BOOLEAN', {'default': True}),
            'rendre_la_vram_apres': ('BOOLEAN', {'default': True}),
        }, 'optional': {
            'paquets_personnages': ('STRING', {'multiline': True, 'default': ''}),
            'chercher_dans_la_bibliotheque': ('BOOLEAN', {'default': True}),
        }}

    RETURN_TYPES = ('STRING', 'STRING', 'STRING', 'AUDIO')
    RETURN_NAMES = ('dossier', 'resume', 'resultats_json', 'audio_enchaine')
    FUNCTION = 'speak'
    CATEGORY = CATEGORY

    def speak(self, liste, nom, langue, taille_lot, precision, verifier_seulement,
              liberer_vram_comfyui, rendre_la_vram_apres, paquets_personnages='',
              chercher_dans_la_bibliotheque=True):
        parameters = {'text': liste, 'name': nom, 'batch_size': int(taille_lot),
                      'precision': precision, 'dry_run': bool(verifier_seulement),
                      'language': '' if langue == OWN_LANGUAGE else langue}
        bundles = [line.strip().strip('"') for line in (paquets_personnages or '').splitlines()
                   if line.strip()]
        operation = 'speak_batch'
        if bundles or not chercher_dans_la_bibliotheque:
            operation = 'speak_batch_file'
            parameters.update(personas=bundles, use_library=bool(chercher_dans_la_bibliotheque))
        if not verifier_seulement:
            free_comfyui_memory(liberer_vram_comfyui)
        try:
            outputs = run(operation, parameters)
        finally:
            if not verifier_seulement:
                give_back(rendre_la_vram_apres, 'release_voice')
        if outputs.get('dryRun'):
            summary = '%d réplique(s) : %d prête(s), %d impossible(s).' % (
                outputs['lines'], outputs['ready'], outputs['failed'])
            return ('', summary, dumps(outputs.get('preview', [])), silence())
        folder = Path(outputs['folder'])
        results = json.loads((folder / 'resultats.json').read_text(encoding='utf-8'))
        takes = [folder / line['file'] for line in results['lines']
                 if line.get('status') == 'ok' and (folder / line['file']).is_file()]
        summary = '%d/%d réplique(s) écrite(s), %d en échec — %s' % (
            outputs['done'], outputs['lines'], outputs['failed'], folder)
        return (str(folder), summary, dumps(results), join_audio(takes))


class Operation:
    """Any operation of the Tool with its parameters as JSON: the whole of PersonaRP."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'operation': (operations(),),
            'parametres_json': ('STRING', {'multiline': True, 'default': '{}'}),
        }}

    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('resultat_json',)
    FUNCTION = 'call'
    CATEGORY = CATEGORY

    @classmethod
    def IS_CHANGED(cls, **_):
        return float('nan')

    def call(self, operation, parametres_json):
        try:
            parameters = json.loads(parametres_json or '{}')
        except ValueError as exc:
            raise RuntimeError('PersonaRP — parametres_json illisible : %s' % exc) from exc
        return (dumps(run(operation, parameters)),)


NODE_CLASS_MAPPINGS = {
    'PersonaRP_Character': Character,
    'PersonaRP_Dialogue': Dialogue,
    'PersonaRP_Voice': Voice,
    'PersonaRP_ScenePrompts': ScenePrompts,
    'PersonaRP_Translate': Translate,
    'PersonaRP_ReadPhoto': ReadPhoto,
    'PersonaRP_VoiceTask': VoiceTask,
    'PersonaRP_Operation': Operation,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'PersonaRP_Character': 'Personnage (PersonaRP)',
    'PersonaRP_Dialogue': 'Dialogue (PersonaRP)',
    'PersonaRP_Voice': 'Voix (PersonaRP)',
    'PersonaRP_ScenePrompts': 'Prompts de scène (PersonaRP)',
    'PersonaRP_Translate': 'Traduire (PersonaRP)',
    'PersonaRP_ReadPhoto': 'Lire une photo (PersonaRP)',
    'PersonaRP_VoiceTask': 'Tâche de voix (PersonaRP)',
    'PersonaRP_Operation': 'Opération PersonaRP (avancé)',
}
