from kabot.agent.loop_core import execution_runtime
from kabot.agent.loop_core.execution_runtime_parts import helpers, llm


def test_execution_runtime_uses_refactor_subpackage():
    assert execution_runtime._sanitize_error is helpers._sanitize_error
    assert execution_runtime._resolve_expected_tool_for_query is helpers._resolve_expected_tool_for_query


def test_execution_runtime_uses_llm_submodule():
    assert execution_runtime.run_simple_response is llm.run_simple_response
    assert execution_runtime.call_llm_with_fallback is llm.call_llm_with_fallback
