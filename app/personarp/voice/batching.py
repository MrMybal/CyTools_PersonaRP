"""Speaking many lines at once: the passages of every line, generated in batches.

A batch is the efficient way to fill a large GPU. Qwen3-TTS takes a list of texts in one
call — each with its own voice, language and direction — so one copy of the model serves
many lines at a time, instead of several copies competing for the same card.

Every line is first cut into its plan (passages and silences, see annotations.py). The
passages of all the lines are pooled, ordered by length so that a batch holds texts of
similar size (less padding, less waste), and generated in batches whose size is measured,
not guessed: a first small batch — the longest passages, so the dearest — tells what one
passage really costs on this card, with this model and these voices, and the next batches
are sized from the memory left. A batch that still does not fit is split in two and tried
again, down to one passage.

That last guard only works if running out of memory is an error. On Windows the NVIDIA
driver lets CUDA spill into system memory instead, silently and very slowly — a batch of
16 cloned lines once asked for 26 GB on a 24 GB card and ran four times slower than one
line at a time. The worker therefore caps its own memory to what was free when it started
(see tts_worker.synthesize_batch), which turns a spill back into an error.

The standard library only: the voice worker imports this module inside the private engine.
"""

# What one passage is first assumed to cost on top of the weights, before anything has been
# measured. Measured on an RTX 3090 with the 1.7B Base model cloning 15–25 s references:
# about 0.7 GB allocated and 1.2 GB reserved per passage — reserved is what counts.
PER_PASSAGE_BYTES = 1300 * 1024 ** 2
HEADROOM_BYTES = 1536 * 1024 ** 2
MAX_BATCH = 32
CPU_BATCH = 2
# The first batch is kept small: it measures, and a mistake there costs little.
PROBE_BATCH = 4
# Room kept when sizing from a measurement: passages later in the list are shorter, but a
# batch that fails half way costs more than a batch slightly too small.
SAFETY = 0.85


def auto_size(free_bytes, *, per_passage=PER_PASSAGE_BYTES, headroom=HEADROOM_BYTES,
              ceiling=MAX_BATCH):
    """How many passages to try at once with this much free memory (at least one)."""
    if free_bytes is None:
        return CPU_BATCH
    return max(1, min(ceiling, int((free_bytes - headroom) // per_passage)))


def fit(capacity_bytes, per_passage_bytes, ceiling=MAX_BATCH):
    """How many passages fit in `capacity_bytes` at the measured cost of one."""
    if per_passage_bytes <= 0:
        return ceiling
    return max(1, min(ceiling, int(capacity_bytes * SAFETY // per_passage_bytes)))


def collect(lines):
    """Pool the passages of every line. `lines` is a list of (key, plan)."""
    pooled = []
    for key, plan in lines:
        for position, item in enumerate(plan):
            if 'text' in item:
                pooled.append({'line': key, 'position': position, 'item': item})
    # Longest first: similar lengths share a batch, and the dearest batch is measured first.
    pooled.sort(key=lambda passage: len(passage['item']['text']), reverse=True)
    return pooled


def generate_all(passages, size, generate, is_out_of_memory, progress=None, resize=None):
    """Run `generate(chunk) -> [(wave, rate), ...]` over the passages, in batches.

    A batch that runs out of memory is halved and retried; the smaller size is kept for the
    rest of the run. `resize(done)`, called after each batch that fits with the number of
    passages it held, may return the size to use next — measured from what that batch cost.
    Returns ({(line, position): (wave, rate)}, statistics).
    """
    results = {}
    size = max(1, int(size))
    statistics = {'calls': 0, 'retries': 0, 'firstSize': size, 'size': size, 'sizes': []}
    done = 0
    index = 0
    while index < len(passages):
        chunk = passages[index:index + size]
        try:
            produced = generate(chunk)
        except Exception as exc:                          # noqa: BLE001 - only memory is retried
            if not is_out_of_memory(exc) or len(chunk) == 1:
                raise
            size = max(1, len(chunk) // 2)
            statistics['retries'] += 1
            continue
        if len(produced) != len(chunk):
            raise RuntimeError('The model returned %d takes for %d passages.'
                               % (len(produced), len(chunk)))
        for passage, output in zip(chunk, produced):
            results[(passage['line'], passage['position'])] = output
        statistics['calls'] += 1
        statistics['sizes'].append(len(chunk))
        index += len(chunk)
        done += len(chunk)
        if resize is not None:
            wanted = resize(len(chunk))
            # A size that already failed is not tried again.
            if wanted and not (statistics['retries'] and wanted > size):
                size = max(1, int(wanted))
        if progress:
            progress(done, len(passages), size)
    statistics['size'] = size
    return results, statistics
