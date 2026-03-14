import subprocess
from pathlib import Path

from kabot.cli.agent_smoke_matrix import (
    SmokeCase,
    SmokeResult,
    _create_mcp_local_echo_case,
    _create_mcp_local_echo_continuity_case,
    _print_human_summary,
    _create_web_search_no_key_smoke_cases,
    _localized_weekday_expectations,
    _stdout_matches_expectations,
    apply_thresholds,
    build_agent_command,
    build_continuity_smoke_cases,
    build_memory_smoke_cases,
    build_delivery_smoke_cases,
    build_regression_smoke_cases,
    build_workflow_smoke_cases,
    build_smoke_cases,
    main,
    parse_run_metrics,
    run_case,
    serialize_results_json,
)

JA_PROMPT = "\u4eca\u65e5\u306f\u4f55\u66dc\u65e5\uff1f\u4e00\u884c\u3060\u3051\u3002"
JA_REPLY = "\u4eca\u65e5\u306f\u6708\u66dc\u65e5\u3067\u3059\u3002"


def test_build_smoke_cases_windows_uses_windows_style_path_prompt():
    cases = build_smoke_cases(cwd=Path(r"C:\Users\Arvy Kairi\Desktop\bot\kabot"), os_profile="windows")

    filesystem_case = next(case for case in cases if case.label == "fs-local-id")
    zh_case = next(case for case in cases if case.label == "zh-day")
    ja_case = next(case for case in cases if case.label == "ja-day")
    th_case = next(case for case in cases if case.label == "th-day")

    assert "C:\\" in filesystem_case.prompt
    assert "folder" in filesystem_case.prompt.lower()
    assert "?" not in zh_case.prompt
    assert "?" not in ja_case.prompt
    assert "?" not in th_case.prompt


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
            "2026-03-09 | INFO | turn_id=abc continuity_source=answer_reference turn_category=chat",
            '2026-03-09 | INFO | runtime_event={"event":"route_decision","route_profile":"GENERAL","route_complex":false,"turn_category":"chat","continuity_source":"answer_reference","required_tool":"weather","required_tool_query":"cek suhu cilacap sekarang","external_skill_lane":false,"forced_skill_names":[]}',
            "2026-03-09 | INFO | pending_interrupt_count=2 session=cli:smoke:test",
            "2026-03-09 | INFO | completion_evidence artifact_verified=true delivery_verified=true executed_tools=write_file,message",
            "2026-03-09 | INFO | turn_id=abc context_build_ms=12",
            "2026-03-09 | INFO | turn_id=abc first_response_ms=345",
        )
    )

    metrics = parse_run_metrics(stderr)

    assert metrics["route"] == "Route: profile=GENERAL, complex=False"
    assert metrics["continuity_source"] == "answer_reference"
    assert metrics["turn_category"] == "chat"
    assert metrics["pending_interrupt_count"] == 2
    assert metrics["completion_artifact_verified"] is True
    assert metrics["completion_delivery_verified"] is True
    assert metrics["context_build_ms"] == 12
    assert metrics["first_response_ms"] == 345
    assert metrics["route_decision_snapshot"] == {
        "route_profile": "GENERAL",
        "route_complex": False,
        "turn_category": "chat",
        "continuity_source": "answer_reference",
        "required_tool": "weather",
        "required_tool_query": "cek suhu cilacap sekarang",
        "external_skill_lane": False,
        "forced_skill_names": [],
    }


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


def test_print_human_summary_includes_route_decision_snapshot(monkeypatch):
    emitted = {}

    def _capture(text: str) -> None:
        emitted["text"] = text

    monkeypatch.setattr("kabot.cli.agent_smoke_matrix._emit_text", _capture)

    _print_human_summary(
        [
            SmokeResult(
                label="weather-followup",
                prompt="prediksi 3-6 jam kedepan",
                session_id="cli:smoke:test",
                returncode=0,
                stdout="Cilacap forecast...",
                stderr="",
                route="Route: profile=GENERAL, complex=True",
                continuity_source="weather_context",
                turn_category="action",
                route_decision_snapshot={
                    "route_profile": "GENERAL",
                    "route_complex": True,
                    "turn_category": "action",
                    "continuity_source": "weather_context",
                    "required_tool": "weather",
                    "required_tool_query": "cilacap prediksi 3-6 jam kedepan",
                    "external_skill_lane": False,
                    "forced_skill_names": ["weather"],
                },
                passed=True,
            )
        ]
    )

    text = emitted["text"]
    assert "route_snapshot: GENERAL/action tool=weather" in text
    assert "continuity=weather_context" in text
    assert "forced_skills=weather" in text


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


def test_localized_weekday_expectations_match_known_weekday_index():
    expectations = _localized_weekday_expectations(1)

    assert expectations["id"] == ("Selasa",)
    assert expectations["zh"] == ("星期二",)
    assert expectations["ja"] == ("火曜日",)
    assert expectations["th"] == ("วันอังคาร", "อังคาร")


def test_stdout_matches_expectations_case_insensitively():
    assert _stdout_matches_expectations(
        "Absolutely—I can use BlueBubbles.",
        expected_contains=(),
        expected_any_contains=("bluebubbles", "skill"),
    )


def test_stdout_matches_expectations_ignores_separator_differences():
    assert _stdout_matches_expectations(
        "I will use Test-Driven Development (TDD) for this request.",
        expected_contains=(),
        expected_any_contains=("test-driven-development",),
    )


def test_stdout_matches_expectations_respects_forbidden_contains():
    assert _stdout_matches_expectations(
        "The second item is .claude.",
        expected_any_contains=(".claude",),
        forbidden_contains=(".basetemp", ".dockerignore"),
    )
    assert not _stdout_matches_expectations(
        ".basetemp .claude .dockerignore",
        expected_any_contains=(".claude",),
        forbidden_contains=(".basetemp",),
    )


def test_run_case_returns_failed_result_when_subprocess_times_out(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["python", "-m", "kabot.cli.commands"], timeout=30)

    monkeypatch.setattr("kabot.cli.agent_smoke_matrix.subprocess.run", _boom)

    result = run_case(
        SmokeCase(label="timeout", prompt="Please use the slack skill for this request."),
        cwd=Path.cwd(),
        python_executable="python",
        timeout=30,
    )

    assert result.passed is False
    assert result.returncode == 124
    assert "timeout" in result.failure_reason.lower()


def test_create_mcp_local_echo_case_writes_temp_config(tmp_path):
    case = _create_mcp_local_echo_case(tmp_path, python_executable="python")

    config_path = Path(case.env["KABOT_CONFIG"])
    assert case.label == "mcp-local-echo"
    assert "mcp.local_echo.echo" in case.prompt
    assert config_path.exists()
    assert "\"local_echo\"" in config_path.read_text(encoding="utf-8")


def test_build_continuity_smoke_cases_include_multilingual_followups():
    cases = build_continuity_smoke_cases(
        cwd=Path(r"C:\Users\Arvy Kairi\Desktop\bot\kabot"),
        os_profile="windows",
    )

    zh_case = next(case for case in cases if case.label == "continuity-fs-zh")
    th_case = next(case for case in cases if case.label == "continuity-fs-th")

    assert "C:\\" in zh_case.prompt
    assert zh_case.followup_prompts
    assert zh_case.expected_continuity_source == "answer_reference"
    assert zh_case.expected_turn_category == "chat"
    assert zh_case.expected_any_contains == (".claude",)
    assert zh_case.forbidden_contains == (".basetemp", ".dockerignore")
    assert "\u7b2c\u4e8c" in zh_case.followup_prompts[0]
    assert th_case.followup_prompts
    assert th_case.expected_continuity_source == "answer_reference"
    assert th_case.expected_turn_category == "chat"
    assert th_case.expected_any_contains == (".claude",)
    assert th_case.forbidden_contains == (".basetemp", ".dockerignore")


def test_build_delivery_smoke_cases_include_create_find_and_generate_send_flows():
    cases = build_delivery_smoke_cases(
        cwd=Path(r"C:\Users\Arvy Kairi\Desktop\bot\kabot"),
        os_profile="windows",
    )

    create_case = next(case for case in cases if case.label == "delivery-create-send")
    find_case = next(case for case in cases if case.label == "delivery-find-send")
    image_case = next(case for case in cases if case.label == "delivery-image-send")

    assert create_case.category == "delivery"
    assert ".smoke_tmp" in create_case.prompt
    assert create_case.expected_any_contains == ("Message sent to",)
    assert create_case.expected_turn_category == "action"
    assert create_case.expected_delivery_verified is True

    assert find_case.category == "delivery"
    assert "CHANGELOG.md" in find_case.prompt
    assert "folder kerja saat ini" in find_case.prompt.lower()
    assert find_case.expected_any_contains == ("Message sent to",)
    assert find_case.expected_turn_category == "action"
    assert find_case.expected_delivery_verified is True

    assert image_case.category == "delivery"
    assert "imagen" in image_case.prompt.lower()
    assert image_case.expected_turn_category == "action"
    assert image_case.expected_any_contains == (
        "Message sent to",
        "isn't available in this runtime yet",
        "Configure a supported image provider first",
    )
    assert image_case.forbidden_contains == (
        "I couldn't verify delivery because no file attachment was sent",
        "File not found",
    )


def test_build_memory_smoke_cases_include_cross_lingual_followups():
    cases = build_memory_smoke_cases()

    id_case = next(case for case in cases if case.label == "memory-followup-id-en")
    zh_case = next(case for case in cases if case.label == "memory-followup-zh-id")
    th_case = next(case for case in cases if case.label == "memory-followup-th-en")

    assert id_case.category == "memory"
    assert "MEMID-271" in id_case.prompt
    assert id_case.followup_prompts == ("what is my preference code? answer with the code only.",)
    assert id_case.expected_any_contains == ("MEMID-271",)
    assert id_case.expected_turn_category == "chat"

    assert zh_case.category == "memory"
    assert "MEMZH-314" in zh_case.prompt
    assert zh_case.followup_prompts == ("我刚才让你记住的代码是什么？只回答代码。",)
    assert zh_case.expected_any_contains == ("MEMZH-314",)
    assert zh_case.expected_turn_category == "chat"

    assert th_case.category == "memory"
    assert "MEMTH-808" in th_case.prompt
    assert th_case.followup_prompts == ("what is my preference code? answer with the code only.",)
    assert th_case.expected_any_contains == ("MEMTH-808",)
    assert th_case.expected_turn_category == "chat"


def test_build_workflow_smoke_cases_include_ping_pong_upgrade_transcript():
    cases = build_workflow_smoke_cases()

    ping_pong_case = next(case for case in cases if case.label == "workflow-pingpong-upgrade")
    status_case = next(case for case in cases if case.label == "workflow-status-server-followup")
    weather_case = next(case for case in cases if case.label == "workflow-weather-forecast-followup")

    assert ping_pong_case.category == "workflow"
    assert ping_pong_case.prompt == "create a ping pong game web based"
    assert ping_pong_case.followup_prompts == ("yes continue", "yes continue to upgrade")
    assert ping_pong_case.expected_any_contains == ("ping-pong", "ping pong", "upgrade")
    assert ping_pong_case.forbidden_contains == ("File not found", "/↓", "/↑")

    assert status_case.category == "workflow"
    assert status_case.prompt == "status server gimana"
    assert status_case.followup_prompts == ("ya cek status server sekarang",)
    assert status_case.expected_any_contains == ("server resource monitor", "cpu", "ram", "uptime")
    assert status_case.forbidden_contains == (
        "Results for:",
        "I couldn't verify completion because no tool or skill execution happened",
    )

    assert weather_case.category == "workflow"
    assert weather_case.prompt == "oke untuk cuaca cilacap sekarang berapa"
    assert weather_case.followup_prompts == (
        "maksudnya suhunya lumayan panas untuk keluar rumah",
        "prediksi 3-6 jam kedepan",
        "prediksi",
    )
    assert weather_case.expected_any_contains == (
        "cilacap forecast",
        "source: open-meteo (hourly forecast)",
    )
    assert weather_case.expected_continuity_source == "weather_context"
    assert weather_case.expected_turn_category == "action"
    assert weather_case.forbidden_contains == (
        "Created job",
        "Reminder scheduled for later",
        "I couldn't fetch weather for Prediksi",
    )


def test_build_regression_smoke_cases_include_key_transcript_families():
    cases = build_regression_smoke_cases(
        cwd=Path(r"C:\Users\Arvy Kairi\Desktop\bot\kabot"),
        os_profile="windows",
    )

    labels = {case.label for case in cases}

    assert "continuity-fs-zh" in labels
    assert "delivery-find-send" in labels
    assert "memory-followup-id-en" in labels
    assert "workflow-status-server-followup" in labels
    assert "workflow-weather-forecast-followup" in labels


def test_main_regression_cases_runs_regression_pack(monkeypatch, tmp_path):
    seen_labels = []

    def _fake_run_case(case, **_kwargs):
        seen_labels.append(case.label)
        return SmokeResult(
            label=case.label,
            prompt=case.prompt,
            session_id=f"cli:smoke:{case.label}",
            returncode=0,
            stdout="ok",
            stderr="",
            passed=True,
        )

    monkeypatch.setattr("kabot.cli.agent_smoke_matrix.run_case", _fake_run_case)

    exit_code = main(
        [
            "--cwd",
            str(tmp_path),
            "--no-default-cases",
            "--regression-cases",
            "--json",
        ]
    )

    assert exit_code == 0
    assert "continuity-fs-zh" in seen_labels
    assert "delivery-find-send" in seen_labels
    assert "memory-followup-id-en" in seen_labels
    assert "workflow-status-server-followup" in seen_labels


def test_create_mcp_local_echo_continuity_case_writes_temp_config(tmp_path):
    case = _create_mcp_local_echo_continuity_case(tmp_path, python_executable="python")

    config_path = Path(case.env["KABOT_CONFIG"])
    assert case.label == "mcp-local-echo-followup"
    assert "mcp.local_echo.echo" in case.prompt
    assert case.followup_prompts
    assert case.expected_continuity_source == "answer_reference"
    assert case.expected_turn_category == "chat"
    assert case.expected_any_contains == ("halo-mcp-konteks",)
    assert case.forbidden_contains == ("\u305d\u308c\u3063\u3066\u3069\u3046\u3044\u3046\u610f\u5473",)
    assert config_path.exists()


def test_create_web_search_no_key_smoke_cases_write_temp_config_and_blank_envs(tmp_path):
    cases = _create_web_search_no_key_smoke_cases(tmp_path)

    news_case = next(case for case in cases if case.label == "web-search-no-key-news")
    general_case = next(case for case in cases if case.label == "web-search-no-key-general")
    config_path = Path(news_case.env["KABOT_CONFIG"])

    assert config_path.exists()
    assert news_case.category == "web"
    assert general_case.category == "web"
    assert news_case.expected_turn_category == "action"
    assert general_case.expected_turn_category == "action"
    assert news_case.expected_any_contains == ("Results for:",)
    assert "search api key" in general_case.expected_any_contains[0].lower()
    for env_key in (
        "BRAVE_API_KEY",
        "PERPLEXITY_API_KEY",
        "XAI_API_KEY",
        "KIMI_API_KEY",
        "MOONSHOT_API_KEY",
    ):
        assert news_case.env[env_key] == ""
        assert general_case.env[env_key] == ""


def test_run_case_reuses_same_session_for_followup_turns_and_tracks_continuity(monkeypatch):
    calls = []

    def _run(command, **_kwargs):
        calls.append(command)
        prompt = command[command.index("agent") + 2]
        if prompt == "lanjut":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="lanjutan aman",
                stderr="\n".join(
                    (
                        "2026-03-11 | INFO | Route: profile=CHAT, complex=False",
                        "2026-03-11 | INFO | turn_id=abc continuity_source=answer_reference turn_category=chat",
                        "2026-03-11 | INFO | completion_evidence artifact_verified=true delivery_verified=true executed_tools=find_files,message",
                        "2026-03-11 | INFO | turn_id=abc context_build_ms=9",
                        "2026-03-11 | INFO | turn_id=abc first_response_ms=21",
                    )
                ),
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="awal aman",
            stderr="\n".join(
                (
                    "2026-03-11 | INFO | Route: profile=GENERAL, complex=True",
                    "2026-03-11 | INFO | turn_id=abc continuity_source=parser turn_category=action",
                    "2026-03-11 | INFO | turn_id=abc context_build_ms=7",
                    "2026-03-11 | INFO | turn_id=abc first_response_ms=18",
                )
            ),
        )

    monkeypatch.setattr("kabot.cli.agent_smoke_matrix.subprocess.run", _run)

    result = run_case(
        SmokeCase(
            label="continuity-followup",
            prompt="awal",
            followup_prompts=("lanjut",),
            expected_continuity_source="answer_reference",
            expected_turn_category="chat",
            expected_delivery_verified=True,
        ),
        cwd=Path.cwd(),
        python_executable="python",
        timeout=30,
    )

    assert len(calls) == 2
    first_session = calls[0][calls[0].index("--session") + 1]
    second_session = calls[1][calls[1].index("--session") + 1]
    assert first_session == second_session
    assert result.continuity_source == "answer_reference"
    assert result.turn_category == "chat"
    assert result.completion_delivery_verified is True
    assert result.passed is True


def test_run_case_fails_when_forbidden_text_appears_in_intermediate_followup_stdout(monkeypatch):
    calls = []

    def _run(command, **_kwargs):
        calls.append(command)
        prompt = command[command.index("agent") + 2]
        if prompt == "yes continue":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="File not found: /↓",
                stderr="2026-03-12 | INFO | turn_id=abc continuity_source=committed_action turn_category=contextual_action",
            )
        if prompt == "yes continue to upgrade":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="upgrade ping-pong game complete",
                stderr="\n".join(
                    (
                        "2026-03-12 | INFO | turn_id=abc continuity_source=committed_action turn_category=contextual_action",
                        "2026-03-12 | INFO | completion_evidence artifact_verified=true delivery_verified=false executed_tools=write_file",
                    )
                ),
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="initial build ready",
            stderr="2026-03-12 | INFO | turn_id=abc continuity_source=parser turn_category=action",
        )

    monkeypatch.setattr("kabot.cli.agent_smoke_matrix.subprocess.run", _run)

    result = run_case(
        SmokeCase(
            label="workflow-pingpong-upgrade",
            prompt="create a ping pong game web based",
            followup_prompts=("yes continue", "yes continue to upgrade"),
            expected_any_contains=("upgrade",),
            forbidden_contains=("File not found", "/↓"),
        ),
        cwd=Path.cwd(),
        python_executable="python",
        timeout=30,
    )

    assert len(calls) == 3
    assert result.passed is False
    assert "forbidden_contains" in result.failure_reason
