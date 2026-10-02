"""Recording from a microphone, with a fake audio stack: no device is opened here.

A real microphone was not recorded by these tests; the window's buttons are for that.
"""
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from gui import recorder                                                    # noqa: E402


class FakeStream:
    """Delivers `seconds` of a 300 Hz tone in 20 ms blocks when started."""
    opened = []

    def __init__(self, samplerate, channels, dtype, device, callback):
        self.rate, self.callback, self.device = samplerate, callback, device
        self.active = False
        FakeStream.opened.append(self)

    def start(self):
        self.active = True
        block = int(self.rate * 0.02)
        t = np.arange(int(self.rate * FakeStream.seconds)) / self.rate
        tone = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
        for start in range(0, len(tone), block):
            self.callback(tone[start:start + block, None], block, None, None)

    def stop(self):
        self.active = False

    def close(self):
        pass


@pytest.fixture()
def microphone(monkeypatch):
    FakeStream.opened, FakeStream.seconds = [], 2.0
    fake = types.SimpleNamespace(
        InputStream=FakeStream,
        query_devices=lambda: [{'name': 'Speakers', 'max_input_channels': 0, 'hostapi': 0},
                               {'name': 'Headset mic', 'max_input_channels': 1, 'hostapi': 0},
                               {'name': 'USB mic', 'max_input_channels': 2, 'hostapi': 0},
                               {'name': 'USB mic', 'max_input_channels': 2, 'hostapi': 1}],
        default=types.SimpleNamespace(device=(2, 0)))
    monkeypatch.setitem(sys.modules, 'sounddevice', fake)
    return fake


def test_only_devices_that_record_are_offered_once_the_default_first(microphone):
    assert recorder.input_devices() == [(2, 'USB mic'), (1, 'Headset mic')]


def test_a_recording_is_written_to_data_inputs_as_a_wav(microphone, tmp_path):
    taker = recorder.Recorder(tmp_path / 'inputs')
    assert taker.start('voice', limit=30.0, device=1)
    assert FakeStream.opened[0].device == 1 and taker.recording
    assert abs(taker.seconds - 2.0) < 0.05 and taker.level > 0.1
    path = Path(taker.stop())
    assert path.parent == tmp_path / 'inputs' and path.name.startswith('micro-voice-')
    audio, rate = sf.read(str(path))
    assert rate == recorder.RATE and abs(len(audio) / rate - 2.0) < 0.05
    assert not taker.recording


def test_the_limit_is_seen_and_a_click_is_not_a_recording(microphone, tmp_path):
    taker = recorder.Recorder(tmp_path)
    taker.start('dictation', limit=1.5)
    assert taker.reached_limit()
    FakeStream.seconds = 0.1
    taker.start('dictation', limit=10.0)
    assert taker.stop() == '' and not list(tmp_path.glob('*.wav'))


def test_a_microphone_that_cannot_open_is_explained(monkeypatch, tmp_path):
    def refuse(**kwargs):
        raise OSError('Device unavailable')
    monkeypatch.setitem(sys.modules, 'sounddevice', types.SimpleNamespace(InputStream=refuse))
    taker = recorder.Recorder(tmp_path)
    assert taker.start('voice') is False and not taker.recording
    assert taker.error.startswith('The microphone could not be opened: ')
