"""Fit the assembled prompt to the model's real context, using the model's own tokenizer.

prompting.py already trims on a character budget, which is cheap and works without a loaded
model. This is the second pass: once the server is up it can count actual tokens, so the
history is cut at a user turn rather than guessed at.
"""
from cytools_core import CyToolError

CONTEXT_TOKENS = 16384


def fit_messages(messages, count_tokens, response_tokens, context_tokens=CONTEXT_TOKENS):
    budget = context_tokens - response_tokens - 64
    required = [messages[0], messages[-1]]
    required_tokens = count_tokens(required)
    if required_tokens > budget:
        raise CyToolError(
            'ContextTooLong',
            'The character sheet, world and current message exceed the model context. Lower the '
            'context budget on the sheet, shorten the world, or reduce the reply length.',
            details={'requiredTokens': required_tokens, 'availablePromptTokens': budget,
                     'contextTokens': context_tokens, 'responseTokens': response_tokens},
            recoverable=True)
    total = count_tokens(messages)
    if total <= budget:
        return messages, {'promptTokens': total, 'contextTokens': context_tokens,
                          'responseTokens': response_tokens, 'droppedMessages': 0}
    history = messages[1:-1]
    # Only cut at user turns, so complete recent exchanges are retained.
    cuts = [i for i, item in enumerate(history) if item['role'] == 'user'] + [len(history)]
    low, high = 0, len(cuts) - 1
    while low < high:
        middle = (low + high) // 2
        if count_tokens([messages[0], *history[cuts[middle]:], messages[-1]]) <= budget:
            high = middle
        else:
            low = middle + 1
    cut = cuts[low]
    fitted = [messages[0], *history[cut:], messages[-1]]
    return fitted, {'promptTokens': count_tokens(fitted), 'contextTokens': context_tokens,
                    'responseTokens': response_tokens, 'droppedMessages': cut}
