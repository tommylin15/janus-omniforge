"""Existing approved transports only; adding a model requires a code review."""
MODEL_OPTIONS = {
    'codex_cli': ('gpt-6.1-sol', 'account_default'),
    'openrouter': ('openrouter/free',),
    'gemini': ('gemini-3.5-flash-lite', 'gemini-2.5-flash'),
}
DEFAULT_MODELS = {provider: values[0] for provider, values in MODEL_OPTIONS.items()}


def validated_models(value):
    if not isinstance(value, dict) or set(value) != set(MODEL_OPTIONS):
        raise ValueError('three approved provider models required')
    if any(model not in MODEL_OPTIONS[provider] for provider, model in value.items()):
        raise ValueError('unapproved provider model')
    return dict(value)
