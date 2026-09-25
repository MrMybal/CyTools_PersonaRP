"""Whisper worker, running inside the private voice engine.

Two uses, one model: getting the exact words of a reference take so a cloned voice knows
what it is imitating, and dictating a message to a character instead of typing it.

transcribe {"model_dir": "<dir>", "input": "<audio>", "language": "" (auto) | "fr" | ...,
            "device": "cuda|cpu", "timestamps": true}
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workers._protocol import serve, WorkerError, memory_report  # noqa: E402

_state = {}


def _load(model_dir, device, reporter):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    key = (str(model_dir), device)
    if _state.get('key') == key:
        return _state['pipe']
    unload({}, reporter)
    if device == 'cuda' and not torch.cuda.is_available():
        raise WorkerError('MissingDependency',
                          'CUDA is not available in the voice engine; choose the CPU device.',
                          recoverable=True)
    if not Path(model_dir, 'config.json').is_file():
        raise WorkerError('MissingModel', 'Whisper weights not found: ' + str(model_dir),
                          recoverable=True)
    reporter.progress(5, step='Loading Whisper')
    dtype = torch.float16 if device == 'cuda' else torch.float32
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        str(model_dir), dtype=dtype, low_cpu_mem_usage=True, use_safetensors=True,
        local_files_only=True).to(device)
    processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True)
    pipe = pipeline('automatic-speech-recognition', model=model, tokenizer=processor.tokenizer,
                    feature_extractor=processor.feature_extractor, dtype=dtype, device=device)
    _state.update(key=key, pipe=pipe)
    reporter.resident(model=str(model_dir), gpu=device == 'cuda')
    return pipe


def unload(request, reporter):
    _state.clear()
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    reporter.resident()
    return {'unloaded': True}


def transcribe(request, reporter):
    import soundfile as sf
    from scipy.signal import resample_poly
    started = time.monotonic()
    source = Path(request['input'])
    if not source.is_file():
        raise WorkerError('MissingInput', 'Recording not found: ' + str(source))
    pipe = _load(request['model_dir'], request.get('device', 'cuda'), reporter)
    reporter.progress(20, step='Reading the recording')
    try:
        audio, rate = sf.read(str(source), dtype='float32', always_2d=True)
    except Exception as exc:                                   # noqa: BLE001 - reported to the user
        raise WorkerError('InvalidInput',
                          'This file could not be read as audio (%s). Supply a WAV or FLAC.' % exc)
    mono = audio.mean(axis=1)
    if rate != 16000:
        from math import gcd
        step = gcd(int(rate), 16000)
        mono = resample_poly(mono, 16000 // step, int(rate) // step).astype('float32')
    duration = len(mono) / 16000.0
    if duration < 0.2:
        raise WorkerError('InvalidInput', 'The recording is too short to transcribe.')
    reporter.progress(35, step='Transcribing', message='%.1f s' % duration)
    options = {'return_timestamps': bool(request.get('timestamps', True))}
    generate = {'task': 'transcribe'}
    if request.get('language'):
        generate['language'] = request['language']
    options['generate_kwargs'] = generate
    if duration > 30:
        options['chunk_length_s'] = 30
        options['batch_size'] = 8
    result = pipe({'raw': mono, 'sampling_rate': 16000}, **options)
    segments = []
    for chunk in result.get('chunks') or []:
        stamp = chunk.get('timestamp') or (None, None)
        segments.append({'start': stamp[0], 'end': stamp[1], 'text': chunk.get('text', '').strip()})
    reporter.progress(100, step='Transcribed')
    return {'text': (result.get('text') or '').strip(), 'segments': segments,
            'durationSeconds': duration, 'seconds': round(time.monotonic() - started, 3),
            **memory_report()}


def diagnose(request, reporter):
    import torch
    import transformers
    return {'torch': torch.__version__, 'transformers': transformers.__version__,
            'cuda': torch.cuda.is_available(), 'resident': _state.get('key', ('',))[0]}


HANDLERS = {'transcribe': transcribe, 'unload': unload, 'diagnose': diagnose, 'status': diagnose}

if __name__ == '__main__':
    raise SystemExit(serve(HANDLERS))
