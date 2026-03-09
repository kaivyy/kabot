from kabot.agent import loop
from kabot.agent.loop_parts import compat, delegates


def test_loop_module_uses_refactor_subpackage():
    assert loop.__getattr__ is compat.lazy_compat_getattr
    assert issubclass(loop.AgentLoop, delegates.AgentLoopDelegatesMixin)
