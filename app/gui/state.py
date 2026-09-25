"""Application state for the desktop window.

Everything the window does goes through the same Runtime as the CLI and MCP: there is no
second scheduler and no model loaded inside the UI process. Short library reads are
submitted and waited on inline because they are file reads; anything that loads weights or
touches the network is submitted as a job and polled, so the window never freezes and can
always be cancelled.
"""
import json
import os
import subprocess
import time

from cytools_core import CyToolError
from ui_common import tr

from personarp.paths import APP, DATA, SETTINGS, read_json, write_json
from personarp.schemas import normalize_persona, normalize_world

STATE_FILE = SETTINGS / 'desktop.json'
BUSY = ('Queued', 'Running', 'Pending', 'Starting')


def open_path(path):
    if not path:
        return
    if os.name == 'nt':
        os.startfile(str(path))
    else:
        subprocess.Popen(['xdg-open', str(path)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


class App:
    def __init__(self, runtime, actor, session):
        self.runtime = runtime
        self.actor = actor
        self.session = session
        self.job = None
        self.purpose = ''
        self.consumed = ''
        self.error = ''
        self.notice = ''
        self.pending = []
        self.result = {}

        saved = read_json(STATE_FILE)
        self.persona_id = saved.get('persona_id', '')
        self.session_id = saved.get('session_id', '')
        self.draft = saved.get('draft', '')
        self.updates = read_json(SETTINGS / 'updates.json',
                                 {'repository': '', 'auto_check': False, 'auto_download': False})
        if not (self.updates.get('repository') or '').strip():
            # The repository this application ships with, unless another was chosen.
            self.updates['repository'] = str(read_json(APP / 'release.json', {})
                                             .get('repository') or '')
        self.dirty = False
        self.world_dirty = False

        self.personas = []
        self.worlds = []
        self.persona = None
        self.world = None
        self.conversation = None
        self.turns = []
        self.models = []
        self.engine = {}
        self.diagnosis = {}
        self.images = []
        self.viewing = ''
        self.threads = []
        self.thread = None
        self.thread_id = saved.get('thread_id', '')
        # The translation settings of the Scene tab, remembered between sessions.
        self.translation = {'language': 'English', 'model': '', 'device': '', 'show': 'both',
                            'character_only': False, **(saved.get('translation') or {})}
        self.renaming = False
        self.voices = []
        self.voice_models = []
        self.voice_engine = {}
        self.take = None
        self.player = None
        self.proposal = None
        self.proposal_target = 'sheet'
        self.proposal_kind = 'persona'
        self.author_request = ''
        self.prompt_preview = ''
        self.refresh_library()
        self.refresh_voices()
        self.refresh_threads()
        self.refresh_images()

    # ------------------------------------------------------------------ jobs

    def call(self, operation, parameters=None, timeout=30, flush=True):
        """Submit and wait. Only for operations that read files and return immediately.

        Pending edits are written first: an operation reads the sheet from disk, so running
        one while the window holds unsaved changes would silently use the old values.
        """
        if flush:
            self.flush()
        job = self.runtime.submit(self.actor, self.session, operation, parameters or {})
        finished = self.runtime.wait(self.actor, job['jobId'], timeout=timeout)
        if finished['state'] != 'Completed':
            raise CyToolError((finished.get('error') or {}).get('code', 'Failed'),
                              (finished.get('error') or {}).get('message', 'Operation failed.'))
        return finished.get('outputs') or {}

    def submit(self, operation, parameters=None, purpose=''):
        """Start a long operation. The window keeps drawing while it runs.

        What you see on the sheet is what runs: any edit still in the window is written
        before the job is queued.
        """
        try:
            self.flush()
            self.job = self.runtime.submit(self.actor, self.session, operation, parameters or {})
            self.purpose = purpose or operation
            self.error = ''
            self.notice = ''
            return True
        except Exception as exc:                                # noqa: BLE001 - shown to the user
            self.error = str(exc)
            return False

    @property
    def busy(self):
        return bool(self.job and self.job['state'] in BUSY)

    def cancel(self):
        if self.job:
            self.runtime.cancel(self.actor, self.job['jobId'])

    def poll(self):
        """Advance the current job and apply its result once."""
        if self.job:
            self.job = self.runtime.get_job(self.actor, self.job['jobId'])
            if self.job['state'] in ('Completed', 'Failed', 'Cancelled') \
                    and self.consumed != self.job['jobId']:
                self.consumed = self.job['jobId']
                if self.job['state'] == 'Completed':
                    self._completed(self.purpose, self.job.get('outputs') or {})
                else:
                    self.error = json.dumps(self.job.get('error')
                                            or {'message': 'Operation cancelled.'},
                                            ensure_ascii=False)
        if self.pending and not self.busy:
            operation, parameters, purpose = self.pending.pop(0)
            self.submit(operation, parameters, purpose)

    def _completed(self, purpose, outputs):
        self.result = outputs
        if purpose == 'chat':
            self.notice = ''
            self.reload_conversation()
            self.refresh_library()
            if outputs.get('audioFile'):
                self.play_file(outputs['audioFile'])
        elif purpose == 'author':
            self.proposal = outputs.get('proposal')
            self.proposal_target = outputs.get('target', self.proposal_target)
            self.proposal_kind = outputs.get('kind', self.proposal_kind)
            self.notice = 'Proposal ready. Review it, then apply it.'
        elif purpose == 'assistant_chat':
            self.thread_id = outputs.get('threadId', self.thread_id)
            self.load_thread()
            self.refresh_threads()
            if outputs.get('truncated'):
                self.notice = ('The reply was cut off at its length limit; raise it in the '
                               'discussion settings.')
        elif purpose == 'list_images':
            self.images = outputs.get('images', [])
        elif purpose == 'describe_image':
            self.proposal = outputs.get('proposal')
            self.proposal_target = 'appearance'
            self.proposal_kind = 'persona'
            self.notice = (tr('Appearance read from the photograph in %.1f s. Review it in '
                              'the Assistant tab, then apply it.') % outputs.get('seconds', 0.0))
        elif purpose == 'list_voice_models':
            self.voice_models = outputs.get('models', [])
            self.voice_engine = {**outputs.get('engine', {}),
                                 'workers': outputs.get('workers', {})}
        elif purpose == 'capture_voice_take':
            self.take = dict(outputs)
            self.notice = (tr('Take of %.1f s ready. Listen to it, then keep it.')
                           % outputs.get('durationSeconds', 0.0))
            self.play_file(outputs.get('file', ''))
        elif purpose == 'create_stable_voice':
            self.take = None
            template = (tr('Stable voice "%s" created and attached.') if outputs.get('attached')
                        else tr('Stable voice "%s" created.'))
            self.notice = (template % outputs.get('id', '') + ' '
                           + outputs.get('warning', '')).strip()
            self.refresh_voices()
            self.load_persona()
        elif purpose in ('install_voice_engine', 'install_voice_model', 'release_voice'):
            self.notice = 'Done.'
            self.pending.append(('list_voice_models', {'verify': False}, 'list_voice_models'))
        elif purpose == 'speak':
            self.notice = self._take_notice(outputs)
            self.play_file(outputs.get('file', ''))
        elif purpose == 'translate':
            self.reload_conversation()
            count = len(outputs.get('translations', []))
            if count:
                self.notice = (tr('%d line(s) translated (%s) by %s in %.1f s.')
                               % (count, tr(outputs.get('language', '')),
                                  outputs.get('model', ''), outputs.get('seconds', 0.0)))
            else:
                self.notice = 'Nothing new to translate: every line already has this language.'
            if outputs.get('marksLost'):
                self.notice += (tr(' %d delivery mark(s) were lost by the model; they are '
                                   'listed under the lines concerned.') % outputs['marksLost'])
            if outputs.get('termsLearned'):
                self.notice += tr(' New terms of the world rendered and kept: %s.') \
                    % ', '.join(outputs['termsLearned'])
                if self.world and self.world.get('id') == outputs.get('worldId'):
                    try:
                        fresh = self.call('get_world', {'world_id': outputs['worldId']},
                                          flush=False)['world']
                        self.world['term_translations'] = fresh.get('term_translations') or {}
                    except CyToolError:
                        pass
            if outputs.get('termsMissed'):
                self.notice += (tr(' %d term(s) of the world were not kept; they are listed '
                                   'under the lines concerned.') % outputs['termsMissed'])
        elif purpose == 'install_comfyui':
            state = getattr(self, 'comfyui_state', None)
            if state is not None:
                state['status'] = None
            self.notice = (tr('PersonaRP nodes installed in %s. Restart ComfyUI to load them.')
                           % outputs.get('folder', ''))
        elif purpose == 'batch_check':
            form = getattr(self, 'batch_form', None)
            if form is not None:
                form['preview'] = outputs
            self.notice = (tr('Task checked: %d line(s) ready, %d cannot be spoken. Nothing was '
                              'generated.') % (outputs.get('ready', 0), outputs.get('failed', 0)))
        elif purpose == 'speak_batch':
            form = getattr(self, 'batch_form', None)
            if form is not None:
                form['last'] = outputs
                form['preview'] = None
                form['batches'] = None
            self.notice = (tr('Task written in %s: %d line(s) done, %d failed.')
                           % (outputs.get('folder', ''), outputs.get('done', 0),
                              outputs.get('failed', 0)))
        elif purpose == 'speak_turn':
            self.reload_conversation()
            self.notice = self._take_notice(outputs)
            self.play_file(outputs.get('file', ''))
        elif purpose == 'list_models':
            self.models = outputs.get('models', [])
            self.engine = outputs.get('engine', {})
        elif purpose == 'diagnose_backend':
            self.diagnosis = outputs
            self.models = outputs.get('models', self.models)
            self.engine = outputs.get('engine', self.engine)
        elif purpose in ('install_llm', 'install_cuda'):
            self.notice = 'Installation finished.'
            self.pending.append(('list_models', {'verify': False}, 'list_models'))
        elif purpose == 'update':
            self.notice = outputs.get('message', 'Done.')
        elif purpose == 'export':
            self.notice = 'Exported to ' + outputs.get('file', '')
        elif purpose == 'import':
            self.examples = None                    # their "already imported" mark changed
            self.notice = tr('Imported %d character(s) and %d world(s).') % (
                len(outputs.get('personas', [])), len(outputs.get('worlds', [])))
            self.refresh_library()

    @staticmethod
    def _take_notice(outputs):
        """Which voice really spoke, so a configuration that did not apply is visible."""
        plan = outputs.get('voicePlan') or {}
        described = {'same': tr('same voice'), 'voice': tr('its own voice for this language'),
                     'design': tr('invented voice'), 'preset': tr('preset speaker')}.get(
                         plan.get('source', ''), '')
        if plan.get('source') == 'same' and plan.get('accent') == 'native':
            described += tr(', native pronunciation')
        text = tr('Take ready (%.1f s)') % outputs.get('durationSeconds', 0.0)
        if plan.get('language'):
            text += ' — %s, %s' % (tr(plan['language']), described or plan.get('mode', ''))
        text += '.'
        if outputs.get('note'):
            text += ' ' + outputs['note']
        return text

    # --------------------------------------------------------------- library

    def refresh_library(self):
        try:
            self.personas = self.call('list_personas').get('personas', [])
            self.worlds = self.call('list_worlds').get('worlds', [])
        except CyToolError as exc:
            self.error = str(exc)
            return
        ids = [entry['id'] for entry in self.personas]
        if self.persona_id not in ids:
            self.persona_id = ids[0] if ids else ''
            self.session_id = ''
        self.load_persona()

    def load_persona(self):
        self.persona = None
        self.world = None
        self.conversation = None
        self.turns = []
        if not self.persona_id:
            return
        try:
            outputs = self.call('get_persona', {'persona_id': self.persona_id})
        except CyToolError as exc:
            self.error = str(exc)
            return
        self.persona = normalize_persona(outputs['persona'])
        self.world = normalize_world(outputs['world']) if outputs.get('world') else None
        self.load_sessions()

    def load_sessions(self):
        try:
            listing = self.call('list_sessions', {'persona_id': self.persona_id}).get('sessions', [])
        except CyToolError as exc:
            self.error = str(exc)
            return
        self.sessions = listing
        if listing and self.session_id not in [s['id'] for s in listing]:
            self.session_id = listing[0]['id']
        if not listing:
            self.session_id = ''
        self.reload_conversation()

    def reload_conversation(self):
        if not (self.persona_id and self.session_id):
            self.conversation = None
            self.turns = []
            return
        try:
            self.conversation = self.call('get_session', {'persona_id': self.persona_id,
                                                          'session_id': self.session_id})['session']
            self.turns = self.conversation.get('turns', [])
        except CyToolError as exc:
            self.error = str(exc)

    def flush(self):
        """Write what the window is holding, so disk and screen agree before anything runs.

        Edits are not saved keystroke by keystroke — a slider drag would write a revision
        per frame — so they are collected and written at the moment they start to matter.
        """
        if self.dirty and self.persona:
            self.save_persona()
        if self.world_dirty and self.world:
            self.save_world()

    def save_persona(self):
        if not self.persona:
            return
        try:
            outputs = self.call('save_persona', {'persona': self.persona}, flush=False)
            self.persona = normalize_persona(outputs['persona'])
            self.notice = tr('Character saved (revision %d).') % outputs['revision']
            self.dirty = False
            self.refresh_library_names()
        except CyToolError as exc:
            self.error = str(exc)

    def save_world(self):
        if not self.world:
            return
        try:
            outputs = self.call('save_world', {'world': self.world}, flush=False)
            self.world = normalize_world(outputs['world'])
            self.world_dirty = False
            self.notice = tr('World saved (revision %d).') % outputs['revision']
        except CyToolError as exc:
            self.error = str(exc)

    def refresh_library_names(self):
        try:
            self.personas = self.call('list_personas').get('personas', [])
            self.worlds = self.call('list_worlds').get('worlds', [])
        except CyToolError as exc:
            self.error = str(exc)

    def select_persona(self, identifier):
        self.flush()
        self.persist()
        self.persona_id = identifier
        self.session_id = ''
        self.draft = ''
        self.result = {}
        self.prompt_preview = ''
        self.load_persona()

    def ensure_session(self):
        if self.session_id:
            return self.session_id
        if not self.persona_id:
            raise CyToolError('InvalidParameters', 'Create a character first.')
        outputs = self.call('new_session', {'persona_id': self.persona_id})
        self.session_id = outputs['id']
        self.load_sessions()
        return self.session_id

    # --------------------------------------------------------------- pictures

    def refresh_images(self):
        try:
            self.images = self.call('list_images', {}).get('images', [])
        except CyToolError as exc:
            self.error = str(exc)
        if self.viewing and self.viewing not in {item.get('file') for item in self.images}:
            self.viewing = ''

    # ------------------------------------------------------------ discussion

    def refresh_threads(self):
        try:
            self.threads = self.call('list_assistant_threads', {}).get('threads', [])
        except CyToolError as exc:
            self.error = str(exc)
            return
        known = [entry['id'] for entry in self.threads]
        if self.thread_id not in known:
            self.thread_id = known[0] if known else ''
        self.load_thread()

    def load_thread(self):
        self.thread = None
        if not self.thread_id:
            return
        try:
            self.thread = self.call('get_assistant_thread',
                                    {'thread_id': self.thread_id})['thread']
        except CyToolError as exc:
            self.error = str(exc)

    def select_thread(self, identifier):
        """Switching tabs keeps what was being typed in the one we are leaving."""
        if identifier == self.thread_id:
            return
        self.save_thread_draft()
        self.thread_id = identifier
        self.renaming = False
        self.load_thread()

    def save_thread_draft(self):
        """Write the unsent draft, the title and the settings of the open discussion."""
        if not self.thread:
            return
        try:
            self.call('save_assistant_thread', {
                'thread_id': self.thread['id'], 'title': self.thread.get('title', ''),
                'system': self.thread.get('system', ''), 'draft': self.thread.get('draft', ''),
                'llm_model': self.thread.get('llm_model', ''),
                'device': self.thread.get('device', ''),
                'temperature': self.thread.get('temperature'),
                'response_length': self.thread.get('response_length')})
        except CyToolError as exc:
            self.error = str(exc)

    # ----------------------------------------------------------------- voice

    def refresh_voices(self):
        """Voices and engine state are file reads, so the window can show them on frame one
        instead of announcing "not installed" until a background job answers."""
        try:
            self.voices = self.call('list_voices', {}).get('voices', [])
            outputs = self.call('list_voice_models', {'verify': False}, timeout=60)
            self.voice_models = outputs.get('models', [])
            self.voice_engine = {**outputs.get('engine', {}),
                                 'workers': outputs.get('workers', {})}
        except CyToolError as exc:
            self.error = str(exc)

    def play_file(self, path):
        """Play a take. The player is created on first use so no audio device is opened
        before there is something to hear."""
        if not path:
            return
        try:
            if self.player is None:
                from .player import Player
                self.player = Player()
            self.player.load(path)
            self.player.play()
        except Exception as exc:                              # noqa: BLE001 - shown to the user
            self.error = 'Playback: %s' % exc

    def stop_audio(self):
        if self.player is not None:
            try:
                self.player.stop()
            except Exception:                                 # noqa: BLE001 - closing anyway
                pass

    # --------------------------------------------------------------- persist

    def persist(self):
        # A smoke run that opens a throwaway character must not leave it selected for you.
        if not getattr(self, 'ephemeral', False):
            write_json(STATE_FILE, {'persona_id': self.persona_id,
                                    'session_id': self.session_id, 'draft': self.draft,
                                    'thread_id': self.thread_id,
                                    'translation': self.translation})
        self.save_thread_draft()
        write_json(SETTINGS / 'updates.json', self.updates)
        self.flush()

    # -------------------------------------------------------- generation config

    def capture_config(self):
        return {'operationId': 'chat',
                'parameters': {'persona_id': self.persona_id, 'text': self.draft,
                               'session_id': self.session_id}}

    def restore_config(self, value):
        if value.get('operationId') != 'chat':
            raise ValueError('Load a conversation configuration here.')
        parameters = value.get('parameters', {})
        if parameters.get('persona_id'):
            self.select_persona(parameters['persona_id'])
        self.draft = parameters.get('text', '')
