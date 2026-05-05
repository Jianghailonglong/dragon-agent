from core.hook import AgentHook, CompositeHook, HookContext


class RecordingHook(AgentHook):
    def __init__(self):
        self.calls = []

    def before_iteration(self, ctx):
        self.calls.append(("before_iteration", ctx.iteration))

    def after_iteration(self, ctx):
        self.calls.append(("after_iteration", ctx.iteration))

    def finalize_content(self, ctx, content):
        self.calls.append(("finalize_content", content))
        return content.upper()


def test_base_hook_noop():
    hook = AgentHook()
    ctx = HookContext(iteration=0)
    hook.before_iteration(ctx)
    assert hook.finalize_content(ctx, "test") == "test"
    assert hook.wants_streaming() is False


def test_composite_hook_calls_all():
    h1 = RecordingHook()
    h2 = RecordingHook()
    composite = CompositeHook([h1, h2])

    ctx = HookContext(iteration=0)
    composite.before_iteration(ctx)

    assert h1.calls == [("before_iteration", 0)]
    assert h2.calls == [("before_iteration", 0)]


def test_composite_finalize_chains():
    h1 = RecordingHook()
    h2 = RecordingHook()
    composite = CompositeHook([h1, h2])

    ctx = HookContext(iteration=0)
    result = composite.finalize_content(ctx, "hello")
    assert result == "HELLO"  # both upper(), last one wins


def test_composite_add():
    composite = CompositeHook()
    h = RecordingHook()
    composite.add(h)
    composite.before_iteration(HookContext(iteration=5))
    assert h.calls == [("before_iteration", 5)]
