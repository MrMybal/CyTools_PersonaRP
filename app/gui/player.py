"""In-app WAV playback. Importing this module does not open an audio device.

Nothing here talks to the runtime: it plays a file a job already produced, so a scene keeps
its audio even when the speech engine is unloaded.
"""
import shutil
import threading
from pathlib import Path


class Player:
    def __init__(self):
        self.stream = None
        self.samples = None
        self.rate = 1
        self.position = 0
        self.paused = False
        self.path = ''
        self.volume = 1.0
        self.error = ''
        self.lock = threading.Lock()

    def load(self, path):
        import soundfile as sf
        self.stop()
        self.samples, self.rate = sf.read(str(path), dtype='float32', always_2d=True)
        self.path = str(path)
        self.position = 0
        self.error = ''

    @property
    def duration(self):
        return len(self.samples) / self.rate if self.samples is not None else 0.0

    @property
    def seconds(self):
        return self.position / self.rate if self.samples is not None else 0.0

    @property
    def loaded(self):
        return self.samples is not None

    @property
    def playing(self):
        return bool(self.stream and self.stream.active and not self.paused)

    def play(self):
        import sounddevice as sd
        if self.samples is None:
            return
        if self.position >= len(self.samples):
            self.position = 0
        if self.stream and self.stream.active:
            self.paused = False
            return
        if self.stream:
            self.stream.close()
        self.paused = False

        def callback(out, frames, time, status):
            out.fill(0)
            with self.lock:
                if self.paused:
                    return
                count = min(frames, len(self.samples) - self.position)
                out[:count] = self.samples[self.position:self.position + count] * self.volume
                self.position += count
                if count < frames:
                    raise sd.CallbackStop()

        self.stream = sd.OutputStream(samplerate=self.rate, channels=self.samples.shape[1],
                                      dtype='float32', callback=callback)
        self.stream.start()

    def pause(self):
        self.paused = not self.paused

    def seek(self, seconds):
        with self.lock:
            total = len(self.samples) if self.samples is not None else 0
            self.position = max(0, min(total, int(seconds * self.rate)))

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.position = 0
        self.paused = False

    def export(self, destination):
        if self.path and Path(destination).resolve() != Path(self.path).resolve():
            shutil.copy2(self.path, destination)
        return destination
