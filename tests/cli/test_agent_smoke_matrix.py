from pathlib import Path

from kabot.cli.agent_smoke_matrix import (
    SmokeResult,
    apply_thresholds,
    build_agent_command,
    build_smoke_cases,
    parse_run_metrics,
    serialize_results_json,
)

JA_PROMPT = "\u4eca\u65e5\u306f\u4f55\u66dc\u65e5\uff1f\u4e00\u884c\u3060\u3051\u3002"
JA_REPLY = "\u4eca\u65e5\u306f\u6708\u66dc\u65e5\u3067\u3059\u3002"


def test_build_smoke_cases_windows_uses_windows_style_path_prompt():
    cases = build_smoke_cases(cwd=Path(r"C:\Users\Arvy Kairi\Desktop\bot\kabot"), os_profile="windows")

    filesystem_case = next(case for case in cases if case.label == "fs-local-id")

    assert "C:\\" in filesystem_case.prompt
    assert "folder" in filesystem_case.prompt.lower()


def test_build_smoke_cases_posix_uses_posix_style_path_prompt():
    cases = build_smoke_cases(cwd=Path("/Users/arvy/project/kabot"), os_profile="posix")

    filesystem_case = next(case for case in cases if case.label == "fs-local-id")

    assert "/Users/arvy/project/kabot" in filesystem_case.prompt
    assert "\\" not in filesystem_case.prompt


def test_build_agent_command_uses_argument_list_with_unicode_prompt():
    command = build_agent_command(
        JA_PROMPT,
        session_id="cli:smoke:test",
        python_executable="python",
    )

    assert isinstance(command, list)
    assert command[:4] == ["python", "-X", "utf8", "-m"]
    assert "kabot.cli.commands" in command
    assert command[-6] == "-m"
    assert command[-5] == JA_PROMPT
    assert "--session" in command
    assert command[command.index("--session") + 1] == "cli:smoke:test"


def test_parse_run_metrics_extracts_route_and_latency_values():
    stderr = "\n".join(
        (
            "2026-03-09 | INFO | Route: profile=GENERAL, complex=False",
            "2026-03-09 | INFO | turn_id=abc context_build_ms=12",
            "2026-03-09 | INFO | turn_id=abc first_response_ms=345",
        )
    )

    metrics = parse_run_metrics(stderr)

    assert metrics["route"] == "Route: profile=GENERAL, complex=False"
    assert metrics["context_build_ms"] == 12
    assert metrics["first_response_ms"] == 345


def test_serialize_results_json_preserves_unicode():
    payload = serialize_results_json(
        [
            SmokeResult(
                label="ja-day",
                prompt=JA_PROMPT,
                session_id="cli:smoke:test",
                returncode=0,
                stdout=JA_REPLY,
                stderr="",
                passed=True,
            )
        ]
    )

    assert JA_PROMPT in payload
    assert JA_REPLY in payload


def test_apply_thresholds_marks_slow_first_response_as_failure():
    result = SmokeResult(
        label="id-day",
        prompt="hari apa sekarang?",
        session_id="cli:smoke:test",
        returncode=0,
        stdout="Sekarang hari Senin.",
        stderr="",
        first_response_ms=1200,
        passed=True,
    )

    gated = apply_thresholds(result, max_first_response_ms=500)

    assert gated.passed is False
    assert "first_response_ms" in gated.failure_reason
    assert "500" in gated.failure_reason


def test_apply_thresholds_marks_missing_metric_as_failure_when_gate_enabled():
    result = SmokeResult(
        label="id-day",
        prompt="hari apa sekarang?",
        session_id="cli:smoke:test",
        returncode=0,
        stdout="Sekarang hari Senin.",
        stderr="",
        passed=True,
    )

    gated = apply_thresholds(result, max_context_build_ms=300)

    assert gated.passed is False
    assert "missing context_build_ms" in gated.failure_reason
