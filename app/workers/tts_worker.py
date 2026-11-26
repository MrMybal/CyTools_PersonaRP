"""Qwen3-TTS worker, running inside the private voice engine.

Three ways to produce a voice, all from the same weights:

  custom  a preset speaker, steered by a natural-language instruction
  design  a voice invented from a written description, with no recording at all
  clone   a voice taken from a short reference recording — this is what a character's
          stable voice uses, so every line it ever speaks matches the same take

The model is kept resident between requests; the host unloads it when a job asks for the
resources back or after the idle delay.

synthesize {"model_path": "<dir>", "mode": "custom|clone|design", "text": "...",
            "language": "French", "speaker": "Ryan", "instruction": "",
            "reference_audio": "", "reference_text": "", "x_vector_only": false,
            "device": "cuda|cpu", "delivery": "paragraphs|segments|complete",
            "annotations": true, "temperature": 0.9, "top_k": 50, "top_p": 1.0,
            "repetition_penalty": 1.05, "max_new_tokens": 2048, "seed": 42,
            "output_dir": "<dir inside the workspace>", "workspace": "..."}
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workers._protocol import serve, WorkerError, inside, memory_report  # noqa: E402

_model = None
_model_key = None


PRECISIONS = ('auto', 'bfloat16', 'float16', 'float32')


def resolve_precision(precision, device):
    """The dtype a request really gets.

    auto: bfloat16 where the card computes it natively (compute capability 8 and above:
    A100, L4, RTX 30/40), float16 on older cards such as the T4, float32 on the CPU.
    """
    import torch
    precision = precision if precision in PRECISIONS else 'auto'
    if device != 'cuda':
        return 'float32'
    if precision != 'auto':
        return precision
    major, _ = torch.cuda.get_device_capability(0)
    return 'bfloat16' if major >= 8 else 'float16'


def _load(model_path, device, reporter, precision='auto'):
    global _model, _model_key
    import torch
    from qwen_tts import Qwen3TTSModel
    dtype = resolve_precision(precision, device)
    key = (str(model_path), device, dtype)
    if _model is not None and _model_key == key:
        return _model
    unload({}, reporter)
    if device == 'cuda' and not torch.cuda.is_available():
        raise WorkerError('MissingDependency',
                          'CUDA is not available in the voice engine; choose the CPU device.',
                          recoverable=True)
    if not Path(model_path, 'config.json').is_file():
        raise WorkerError('MissingModel', 'Voice weights not found: ' + str(model_path),
                          recoverable=True)
    reporter.progress(2, step='Loading the voice model', message=Path(model_path).name)
    torch.set_num_threads(min(8, os.cpu_count() or 4))
    _model = Qwen3TTSModel.from_pretrained(
        str(model_path), device_map='cuda:0' if device == 'cuda' else 'cpu',
        dtype=getattr(torch, dtype), attn_implementation='sdpa')
    _model_key = key
    reporter.resident(model=str(model_path), gpu=device == 'cuda')
    return _model


def unload(request, reporter):
    global _model, _model_key
    _model = None
    _model_key = None
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


def synthesize(request, reporter):
    import numpy as np
    import soundfile as sf
    import torch
    from personarp.voice.annotations import AnnotationError, build_plan, render_plan

    started = time.monotonic()
    device = request.get('device', 'cuda')
    model = _load(request['model_path'], device, reporter, request.get('precision', 'auto'))
    torch.manual_seed(int(request.get('seed', 42)) & 0x7fffffff)
    mode = request.get('mode', 'custom')
    try:
        plan = build_plan(request['text'], enabled=bool(request.get('annotations', True)),
                          delivery=request.get('delivery', 'paragraphs'),
                          base_instruction=request.get('instruction', '') or '')
    except AnnotationError as exc:
        raise WorkerError('InvalidParameters', str(exc))

    common = dict(language=request.get('language', 'Auto'),
                  temperature=float(request.get('temperature', 0.9)),
                  top_k=int(request.get('top_k', 50)), top_p=float(request.get('top_p', 1.0)),
                  repetition_penalty=float(request.get('repetition_penalty', 1.05)),
                  max_new_tokens=int(request.get('max_new_tokens', 2048)), do_sample=True)

    prompt = None
    if mode == 'clone':
        reference = request.get('reference_audio') or ''
        if not Path(reference).is_file():
            raise WorkerError('MissingInput', 'Reference recording not found: ' + reference)
        reporter.progress(4, step='Encoding the reference voice')
        prompt = model.create_voice_clone_prompt(
            ref_audio=reference, ref_text=request.get('reference_text') or None,
            x_vector_only_mode=bool(request.get('x_vector_only', False)))

    workspace = request.get('workspace')
    out_dir = inside(workspace, request['output_dir']) if workspace else Path(request['output_dir'])
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks, arrays, timeline = [], [], []
    offset = 0
    passages = [item for item in plan if 'text' in item]

    def synthesize_item(item):
        reporter.progress(5 + 90 * len(chunks) / max(1, len(plan)),
                          step='Speaking', message=item['text'][:80])
        if mode == 'custom':
            waves, rate = model.generate_custom_voice(
                text=item['text'], speaker=request.get('speaker', 'Ryan'),
                instruct=item['instruction'], **common)
        elif mode == 'design':
            waves, rate = model.generate_voice_design(
                text=item['text'], instruct=item['instruction'], **common)
        else:
            waves, rate = model.generate_voice_clone(
                text=item['text'], voice_clone_prompt=prompt, **common)
        return waves[0], rate

    def emit(audio, rate, item):
        nonlocal offset
        path = out_dir / ('segment-%04d.wav' % (len(chunks) + 1))
        sf.write(str(path), audio, rate, subtype='PCM_16')
        timeline.append({**{k: v for k, v in item.items() if k != 'instruction'},
                         'startSample': offset, 'sampleCount': int(len(audio)), 'file': str(path)})
        offset += len(audio)
        arrays.append(audio)
        chunks.append(str(path))
        reporter.progress(5 + 90 * len(chunks) / max(1, len(plan)), step='Passage ready',
                          message='%d/%d' % (len(chunks), len(plan)), currentFile=str(path))

    rate = render_plan(plan, synthesize_item, emit)
    audio = np.concatenate(arrays)
    output = out_dir / 'speech.wav'
    sf.write(str(output), audio, rate, subtype='PCM_16')
    reporter.progress(100, step='Take ready')
    return {'file': str(output), 'sampleRate': int(rate),
            'durationSeconds': float(len(audio)) / rate, 'channels': 1, 'chunks': chunks,
            'segments': timeline, 'passages': len(passages), 'mode': mode,
            'model': request.get('model', ''),
            'generationSeconds': round(time.monotonic() - started, 3), **memory_report()}


def _is_out_of_memory(exc):
    import torch
    return isinstance(exc, torch.cuda.OutOfMemoryError) or 'out of memory' in str(exc).lower()


def synthesize_batch(request, reporter):
    """Speak many lines in one pass of the model: see personarp/voice/batching.py.

    request: {"model_path", "mode", "device", "batch_size": 0 for automatic, "output_dir",
              "workspace", "seed", sampling settings, "items": [{"id", "file", "text",
              "language", "instruction", "speaker", "reference_audio", "reference_text",
              "x_vector_only", "annotations", "delivery"}]}
    Every item of a request uses the same mode and weights; the caller groups them.
    A line that fails is reported with its error; the others are still written.
    """
    import numpy as np
    import soundfile as sf
    import torch
    from personarp.voice import batching
    from personarp.voice.annotations import AnnotationError, build_plan, render_plan

    started = time.monotonic()
    device = request.get('device', 'cuda')
    model = _load(request['model_path'], device, reporter, request.get('precision', 'auto'))
    mode = request.get('mode', 'clone')
    items = request['items']
    workspace = request.get('workspace')
    out_dir = inside(workspace, request['output_dir']) if workspace else Path(request['output_dir'])
    out_dir.mkdir(parents=True, exist_ok=True)

    outcome = {item['id']: {'id': item['id'], 'error': ''} for item in items}
    plans = []
    for item in items:
        try:
            plan = build_plan(item['text'], enabled=bool(item.get('annotations', True)),
                              delivery=item.get('delivery', 'paragraphs'),
                              base_instruction=item.get('instruction', '') or '')
        except AnnotationError as exc:
            outcome[item['id']]['error'] = str(exc)
            continue
        plans.append((item['id'], plan))
    by_id = {item['id']: item for item in items}

    # One voice prompt per reference, however many lines it speaks.
    prompts = {}
    if mode == 'clone':
        reporter.progress(3, step='Encoding the reference voices')
        for key, _ in plans:
            item = by_id[key]
            signature = (item.get('reference_audio'), item.get('reference_text'),
                         bool(item.get('x_vector_only')))
            if signature in prompts:
                continue
            if not Path(item.get('reference_audio') or '').is_file():
                outcome[key]['error'] = 'Reference recording not found.'
                continue
            prompts[signature] = model.create_voice_clone_prompt(
                ref_audio=item['reference_audio'], ref_text=item.get('reference_text') or None,
                x_vector_only_mode=bool(item.get('x_vector_only')))[0]
    plans = [(key, plan) for key, plan in plans if not outcome[key]['error']]

    common = dict(temperature=float(request.get('temperature', 0.9)),
                  top_k=int(request.get('top_k', 50)), top_p=float(request.get('top_p', 1.0)),
                  repetition_penalty=float(request.get('repetition_penalty', 1.05)),
                  max_new_tokens=int(request.get('max_new_tokens', 2048)), do_sample=True)
    torch.manual_seed(int(request.get('seed', 42)) & 0x7fffffff)

    def generate(chunk):
        texts = [passage['item']['text'] for passage in chunk]
        lines = [by_id[passage['line']] for passage in chunk]
        languages = [line.get('language') or 'Auto' for line in lines]
        if mode == 'clone':
            voices = [prompts[(line.get('reference_audio'), line.get('reference_text'),
                               bool(line.get('x_vector_only')))] for line in lines]
            waves, rate = model.generate_voice_clone(text=texts, language=languages,
                                                     voice_clone_prompt=voices, **common)
        elif mode == 'design':
            waves, rate = model.generate_voice_design(
                text=texts, language=languages,
                instruct=[passage['item']['instruction'] for passage in chunk], **common)
        else:
            waves, rate = model.generate_custom_voice(
                text=texts, language=languages,
                speaker=[line.get('speaker') or 'Ryan' for line in lines],
                instruct=[passage['item']['instruction'] for passage in chunk], **common)
        return [(wave, rate) for wave in waves]

    requested = int(request.get('batch_size') or 0)
    passages = batching.collect(plans)
    free = limit = base = None
    measured = {'perPassage': None, 'peak': 0, 'largest': 0}
    cuda = device == 'cuda' and torch.cuda.is_available()
    if cuda:
        torch.cuda.empty_cache()
        free, total = torch.cuda.mem_get_info()
        # What the cap counts is reserved memory — the allocator's cache included — so that
        # is what a passage is measured in too; counting allocated memory alone gave half
        # the real cost and batches that would have had to be split again.
        base = torch.cuda.memory_reserved()
        # Windows lets CUDA spill into system memory rather than fail, and a spilled batch
        # crawls. Capping the allocator at what is free now turns a spill back into an
        # out-of-memory error, which the batching then answers by halving the batch.
        limit = base + free - batching.HEADROOM_BYTES
        torch.cuda.set_per_process_memory_fraction(max(0.05, min(1.0, limit / total)))
        torch.cuda.reset_peak_memory_stats()
    if requested > 0:
        size = requested
    elif cuda:
        # Measure before trusting: the first, dearest passages go in a small batch.
        size = min(batching.PROBE_BATCH, batching.auto_size(free))
    else:
        size = batching.CPU_BATCH

    def resize(done):
        """After a batch that fitted: what one passage cost, and how many fit next."""
        if not cuda:
            return None
        peak = torch.cuda.max_memory_reserved()
        measured['peak'] = max(measured['peak'], peak)
        torch.cuda.reset_peak_memory_stats()
        # The allocator keeps what a batch reserved, so a smaller batch after a larger one
        # looks dearer than it is: only the largest batch so far is a measurement.
        if done >= measured['largest']:
            measured['largest'] = done
            measured['perPassage'] = int(max(1, peak - base) / done)
        return None if requested > 0 else batching.fit(limit - base, measured['perPassage'])

    def progress(done, total, current):
        reporter.progress(5 + 85 * done / max(1, total), step='Speaking in batches',
                          message='%d/%d passages, %d at a time' % (done, total, current))

    def out_of_memory(exc):
        if _is_out_of_memory(exc):
            torch.cuda.empty_cache()
            return True
        return False

    try:
        results, statistics = batching.generate_all(passages, size, generate, out_of_memory,
                                                    progress, resize)
    finally:
        if cuda:
            torch.cuda.set_per_process_memory_fraction(1.0)     # single takes are not capped

    reporter.progress(92, step='Writing the takes')
    for key, plan in plans:
        item = by_id[key]
        arrays = []
        try:
            positions = [position for position, part in enumerate(plan) if 'text' in part]
            queue = iter(positions)
            rate = render_plan(plan, lambda part: results[(key, next(queue))],
                               lambda audio, rate, part: arrays.append(audio))
            audio = np.concatenate(arrays)
            target = out_dir / (item['file'] + '.wav')
            sf.write(str(target), audio, rate, subtype='PCM_16')
            outcome[key].update(file=str(target), durationSeconds=float(len(audio)) / rate,
                                sampleRate=int(rate), passages=len(positions))
        except Exception as exc:                          # noqa: BLE001 - one line, not the batch
            outcome[key]['error'] = str(exc)
    reporter.progress(100, step='Batch written')
    report = {'items': [outcome[item['id']] for item in items], 'mode': mode,
              'model': request.get('model', ''), 'batchSize': max(statistics['sizes'] or [0]),
              'firstBatchSize': statistics['firstSize'], 'batchSizes': statistics['sizes'],
              'calls': statistics['calls'], 'memoryRetries': statistics['retries'],
              'passages': len(passages), 'freeVramBytes': free, 'limitBytes': limit,
              'perPassageBytes': measured['perPassage'],
              'precision': resolve_precision(request.get('precision', 'auto'), device),
              'generationSeconds': round(time.monotonic() - started, 3), **memory_report()}
    if measured['peak']:
        report['vramPeakBytes'] = max(measured['peak'], report.get('vramPeakBytes') or 0)
    return report


def diagnose(request, reporter):
    import importlib.metadata
    import torch
    return {'torch': torch.__version__, 'cuda': torch.cuda.is_available(),
            'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else '',
            'qwenTts': importlib.metadata.version('qwen-tts'),
            'resident': _model_key[0] if _model_key else ''}


HANDLERS = {'synthesize': synthesize, 'synthesize_batch': synthesize_batch, 'unload': unload,
            'diagnose': diagnose, 'status': diagnose}

if __name__ == '__main__':
    raise SystemExit(serve(HANDLERS))
