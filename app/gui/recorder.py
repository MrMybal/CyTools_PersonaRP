"""Recording from a microphone, for dictation and for the take a stable voice is made from.

The window records; the operations only ever receive a WAV file (transcribe,
create_stable_voice), exactly as they do from the CLI or MCP, where a file is given. The
recording is written to data/inputs, where a file named without a path is looked for, and is
never deleted by the Tool.

Importing this module opens no audio device. Nothing is recorded until start() is called
from a button the user pressed, and the recording stops at `limit` seconds at the latest.
"""
import threading
import time
from pathlib import Path

import numpy as np

RATE = 24000                            # what the speech models work at; Whisper resamples


def input_devices():
    """[(index, name)] of the devices that can record, the default one first."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default = sd.default.device[0]                   # a pair (input, output), indexable
        if default is None or int(default) < 0:
            default = sd.query_hostapis(0).get('default_input_device')
        default = int(default)
    except Exception:                                     # noqa: BLE001 - no audio stack
        return []
    # Windows lists each input once per audio API (MME, DirectSound, WASAPI...): keep the API
    # of the default input, so a microphone appears once.
    host = devices[default].get('hostapi') if isinstance(default, int) and 0 <= default < len(devices) \
        else None
    found = [(index, device['name']) for index, device in enumerate(devices)
             if device.get('max_input_channels', 0) > 0
             and (host is None or device.get('hostapi') == host)]
    found.sort(key=lambda item: item[0] != default)
    return found


class Recorder:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.stream = None
        self.blocks = []
        self.lock = threading.Lock()
        self.level = 0.0
        self.started = 0.0
        self.limit = 0.0
        self.rate = RATE
        self.error = ''
        self.purpose = ''
        self.last = ''

    @property
    def recording(self):
        return self.stream is not None

    @property
    def seconds(self):
        with self.lock:
            return sum(len(block) for block in self.blocks) / self.rate

    def start(self, purpose, limit=120.0, device=None):
        """Open the microphone. Returns False, with `error` set, when it cannot be opened."""
        import sounddevice as sd
        self.stop(keep=False)
        self.blocks, self.level, self.error = [], 0.0, ''
        self.purpose, self.limit = purpose, float(limit)

        def callback(data, frames, when, status):
            mono = data[:, 0].copy() if data.ndim > 1 else data.copy()
            with self.lock:
                self.blocks.append(mono)
                self.level = float(np.sqrt(np.mean(np.square(mono)))) if len(mono) else 0.0

        self.rate = RATE
        try:
            try:
                self.stream = sd.InputStream(samplerate=self.rate, channels=1, dtype='float32',
                                             device=device, callback=callback)
            except Exception:                             # noqa: BLE001 - the card's own rate
                self.rate = int(sd.query_devices(device, 'input')['default_samplerate'])
                self.stream = sd.InputStream(samplerate=self.rate, channels=1, dtype='float32',
                                             device=device, callback=callback)
            self.stream.start()
        except Exception as exc:                          # noqa: BLE001 - shown to the user
            self.stream = None
            self.error = 'The microphone could not be opened: %s' % exc
            return False
        self.started = time.monotonic()
        return True

    def reached_limit(self):
        return self.recording and self.seconds >= self.limit

    def stop(self, keep=True):
        """Close the microphone. With keep, write the WAV and return its path ('' if empty)."""
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            finally:
                self.stream = None
        with self.lock:
            audio = np.concatenate(self.blocks) if self.blocks else np.zeros(0, np.float32)
            self.blocks = []
        if not keep or len(audio) < self.rate // 4:         # a click, not a recording
            return ''
        import soundfile as sf
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / ('micro-%s-%s.wav' % (self.purpose or 'recording',
                                                   time.strftime('%Y%m%d-%H%M%S')))
        sf.write(str(path), audio, self.rate, subtype='PCM_16')
        self.last = str(path)
        return self.last


def controls(app, purpose, limit, label):
    """Record / Stop, the time and the level. Returns the WAV just written, else ''."""
    from personarp.paths import DATA
    from ui_common import imgui, raw, tr
    from . import widgets

    recorder = getattr(app, 'recorder', None)
    if recorder is None:
        recorder = app.recorder = Recorder(DATA / 'inputs')
    finished = ''
    if recorder.recording and recorder.purpose == purpose:
        stop = widgets.button(tr('Stop recording') + '##record-' + purpose, 'danger')
        if stop or recorder.reached_limit():
            finished = recorder.stop()
            if not finished:
                app.notice = tr('Nothing was recorded: the recording was too short.')
        else:
            imgui.same_line()
            raw().text_disabled('%.1f / %.0f s' % (recorder.seconds, recorder.limit))
            imgui.same_line()
            imgui.progress_bar(min(1.0, recorder.level * 6.0), (140, 0), tr('level'))
    else:
        imgui.begin_disabled(recorder.recording)          # one microphone, one recording
        if widgets.button(label + '##record-' + purpose):
            if not input_devices():
                app.error = tr('No microphone was found on this machine.')
            elif not recorder.start(purpose, limit, getattr(app, 'microphone', None)):
                app.error = recorder.error
        imgui.end_disabled()
    return finished


def microphone_picker(app):
    """Which input records; the system's default unless another one is chosen."""
    from ui_common import imgui, raw, tr
    devices = getattr(app, 'microphones', None)
    if devices is None:
        devices = app.microphones = input_devices()
    if not devices:
        raw().text_disabled(tr('No microphone was found on this machine.'))
        return
    names = [tr('Default microphone')] + [name for _, name in devices]
    current = getattr(app, 'microphone', None)
    index = next((position + 1 for position, (number, _) in enumerate(devices)
                  if number == current), 0)
    changed, index = imgui.combo(tr('Microphone'), index, names)
    if changed:
        app.microphone = None if index == 0 else devices[index - 1][0]
