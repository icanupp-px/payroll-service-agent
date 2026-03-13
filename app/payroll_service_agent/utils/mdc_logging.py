import contextvars


_mdc_context = contextvars.ContextVar("mdc_context", default={})


class MDC:
    @classmethod
    def set(cls, key, value):
        ctx = _mdc_context.get().copy()
        if key in ctx and ctx[key] == value:
            return
        ctx[key] = value
        _mdc_context.set(ctx)

    @classmethod
    def get(cls, key, default=None):
        return _mdc_context.get().get(key, default)

    @classmethod
    def get_all(cls):
        return _mdc_context.get().copy()

    @classmethod
    def clear(cls):
        _mdc_context.set({})
