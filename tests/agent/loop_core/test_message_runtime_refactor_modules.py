import importlib.util
from types import SimpleNamespace

from kabot.agent.loop_core import message_runtime
from kabot.agent.loop_core.message_runtime_parts import followup, helpers, process_flow, tail


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


def test_process_flow_uses_extracted_turn_helper_submodule():
    assert importlib.util.find_spec(
        "kabot.agent.loop_core.message_runtime_parts.turn_helpers"
    ) is not None

    from kabot.agent.loop_core.message_runtime_parts import turn_helpers

    assert process_flow._looks_like_brief_answer_request is turn_helpers._looks_like_brief_answer_request
    assert process_flow._build_answer_reference_fast_reply is turn_helpers._build_answer_reference_fast_reply
    assert process_flow._resolve_turn_category is turn_helpers._resolve_turn_category


def test_message_runtime_syncs_response_runtime_globals(monkeypatch):
    assert importlib.util.find_spec(
        "kabot.agent.loop_core.message_runtime_parts.response_runtime"
    ) is not None

    from kabot.agent.loop_core.message_runtime_parts import response_runtime

    fake_time = SimpleNamespace(perf_counter=lambda: 123.0)
    fake_logger = SimpleNamespace(info=lambda *_args, **_kwargs: None, warning=lambda *_args, **_kwargs: None)

    def _fake_t(key: str, *args, **kwargs):
        return f"<{key}>"

    def _fake_fast_reply(*_args, **_kwargs):
        return "fast"

    monkeypatch.setattr(message_runtime, "t", _fake_t)
    monkeypatch.setattr(message_runtime, "time", fake_time)
    monkeypatch.setattr(message_runtime, "logger", fake_logger)
    monkeypatch.setattr(message_runtime, "build_temporal_fast_reply", _fake_fast_reply)
    monkeypatch.setattr(message_runtime, "_KEEPALIVE_INITIAL_DELAY_SECONDS", 0.11, raising=False)
    monkeypatch.setattr(message_runtime, "_KEEPALIVE_INTERVAL_SECONDS", 0.22, raising=False)

    message_runtime._sync_process_flow_globals()

    assert response_runtime.t is _fake_t
    assert response_runtime.time is fake_time
    assert response_runtime.logger is fake_logger
    assert response_runtime.build_temporal_fast_reply is _fake_fast_reply
    assert response_runtime._KEEPALIVE_INITIAL_DELAY_SECONDS == 0.11
    assert response_runtime._KEEPALIVE_INTERVAL_SECONDS == 0.22


def test_process_flow_uses_extracted_continuity_runtime_submodule():
    assert importlib.util.find_spec(
        "kabot.agent.loop_core.message_runtime_parts.continuity_runtime"
    ) is not None

    from kabot.agent.loop_core.message_runtime_parts import continuity_runtime

    assert process_flow._apply_continuity_runtime is continuity_runtime._apply_continuity_runtime


def test_message_runtime_syncs_continuity_runtime_globals(monkeypatch):
    assert importlib.util.find_spec(
        "kabot.agent.loop_core.message_runtime_parts.continuity_runtime"
    ) is not None

    from kabot.agent.loop_core.message_runtime_parts import continuity_runtime

    fake_logger = SimpleNamespace(info=lambda *_args, **_kwargs: None, warning=lambda *_args, **_kwargs: None)

    monkeypatch.setattr(message_runtime, "logger", fake_logger)

    message_runtime._sync_process_flow_globals()

    assert continuity_runtime.logger is fake_logger


def test_process_flow_uses_extracted_turn_metadata_submodule():
    assert importlib.util.find_spec(
        "kabot.agent.loop_core.message_runtime_parts.turn_metadata"
    ) is not None

    from kabot.agent.loop_core.message_runtime_parts import turn_metadata

    assert process_flow._finalize_turn_metadata is turn_metadata._finalize_turn_metadata
