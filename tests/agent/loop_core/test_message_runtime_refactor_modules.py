from kabot.agent.loop_core import message_runtime
from kabot.agent.loop_core.message_runtime_parts import followup, helpers, tail


def test_message_runtime_uses_refactor_subpackage():
    assert message_runtime._normalize_text is helpers._normalize_text
    assert message_runtime._resolve_runtime_locale is helpers._resolve_runtime_locale


def test_message_runtime_helpers_use_followup_submodule():
    assert helpers._get_pending_followup_tool is followup._get_pending_followup_tool
    assert helpers._set_last_tool_context is followup._set_last_tool_context


def test_message_runtime_uses_tail_submodule():
    assert message_runtime.process_pending_exec_approval is tail.process_pending_exec_approval
    assert message_runtime.process_system_message is tail.process_system_message
    assert message_runtime.process_isolated is tail.process_isolated
