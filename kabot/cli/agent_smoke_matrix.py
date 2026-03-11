"""Cross-platform smoke matrix runner for `kabot agent`."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from kabot.agent.skills import SkillsLoader
from kabot.config.loader import load_config
from kabot.config.schema import McpServerConfig


@dataclass(frozen=True)
class SmokeCase:
    label: str
    prompt: str
    followup_prompts: tuple[str, ...] = ()
    category: str = "default"
    expected_contains: tuple[str, ...] = ()
    expected_any_contains: tuple[str, ...] = ()
    forbidden_contains: tuple[str, ...] = ()
    expected_continuity_source: str = ""
    expected_turn_category: str = ""
    expected_delivery_verified: bool | None = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class SmokeResult:
    label: str
    prompt: str
    session_id: str
    returncode: int
    stdout: str
    stderr: str
    route: str = ""
    continuity_source: str = ""
    turn_category: str = ""
    pending_interrupt_count: int = 0
    completion_artifact_verified: bool | None = None
    completion_delivery_verified: bool | None = None
    context_build_ms: int | None = None
    first_response_ms: int | None = None
    passed: bool = False
    failure_reason: str = ""


def _localized_weekday_expectations(weekday_index: int) -> dict[str, tuple[str, ...]]:
    normalized = int(weekday_index) % 7
    return {
        "id": (("Senin",), ("Selasa",), ("Rabu",), ("Kamis",), ("Jumat",), ("Sabtu",), ("Minggu",))[normalized],
        "zh": (("星期一",), ("星期二",), ("星期三",), ("星期四",), ("星期五",), ("星期六",), ("星期日",))[normalized],
        "ja": (("月曜日",), ("火曜日",), ("水曜日",), ("木曜日",), ("金曜日",), ("土曜日",), ("日曜日",))[normalized],
        "th": (
            ("วันจันทร์", "จันทร์"),
            ("วันอังคาร", "อังคาร"),
            ("วันพุธ", "พุธ"),
            ("วันพฤหัสบดี", "พฤหัสบดี"),
            ("วันศุกร์", "ศุกร์"),
            ("วันเสาร์", "เสาร์"),
            ("วันอาทิตย์", "อาทิตย์"),
        )[normalized],
    }


def _today_weekday_expectations() -> dict[str, tuple[str, ...]]:
    jakarta_now = datetime.now(ZoneInfo("Asia/Jakarta"))
    return _localized_weekday_expectations(jakarta_now.weekday())


def _stdout_matches_expectations(
    stdout: str,
    *,
    expected_contains: tuple[str, ...] = (),
    expected_any_contains: tuple[str, ...] = (),
    forbidden_contains: tuple[str, ...] = (),
) -> bool:
    text = str(stdout or "")
    folded = text.casefold()

    def _normalize_for_loose_match(value: str) -> str:
        return re.sub(r"[\W_]+", "", str(value or "").casefold())

    normalized_text = _normalize_for_loose_match(text)

    def _contains(expected: str) -> bool:
        expected_folded = str(expected or "").casefold()
        if expected_folded in folded:
            return True
        normalized_expected = _normalize_for_loose_match(expected)
        return bool(normalized_expected) and normalized_expected in normalized_text

    if expected_contains and not all(_contains(expected) for expected in expected_contains):
        return False
    if expected_any_contains and not any(_contains(expected) for expected in expected_any_contains):
        return False
    if forbidden_contains and any(_contains(expected) for expected in forbidden_contains):
        return False
    return True


def _normalize_threshold(value: int | None) -> int | None:
    if value is None:
        return None
    return value if value > 0 else None


def detect_os_profile() -> str:
    return "windows" if os.name == "nt" else "posix"


def _normalize_os_profile(value: str) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized == "auto":
        return detect_os_profile()
    if normalized in {"windows", "win"}:
        return "windows"
    return "posix"


def _skill_prompt(locale: str, skill_name: str) -> str:
    templates = {
        "en": f"Please use the {skill_name} skill for this request.",
        "id": f"Tolong pakai skill {skill_name} untuk request ini ya.",
        "zh": f"\u8bf7\u7528 {skill_name} \u6280\u80fd\u5904\u7406\u8fd9\u4e2a\u8bf7\u6c42\u3002",
        "ja": f"{skill_name} \u30b9\u30ad\u30eb\u3092\u4f7f\u3063\u3066\u3053\u306e\u4f9d\u983c\u3092\u624b\u4f1d\u3063\u3066\u3002",
        "th": f"\u0e0a\u0e48\u0e27\u0e22\u0e43\u0e0a\u0e49\u0e2a\u0e01\u0e34\u0e25 {skill_name} \u0e01\u0e31\u0e1a\u0e07\u0e32\u0e19\u0e19\u0e35\u0e49\u0e2b\u0e19\u0e48\u0e2d\u0e22",
    }
    return templates.get(locale, templates["en"])


def build_smoke_cases(
    *,
    cwd: Path | None = None,
    os_profile: str = "auto",
) -> list[SmokeCase]:
    base_dir = Path(cwd or Path.cwd())
    profile = _normalize_os_profile(os_profile)
    path_text = str(base_dir) if profile == "windows" else base_dir.as_posix()
    weekday_expectations = _today_weekday_expectations()

    return [
        SmokeCase("id-day", "hari apa sekarang? jawab singkat, pakai WIB ya.", expected_contains=weekday_expectations["id"]),
        SmokeCase("id-weird-day", "bro sekarang hari apa sih woi, jawab satu baris", expected_contains=weekday_expectations["id"]),
        SmokeCase("zh-day", "\u4eca\u5929\u661f\u671f\u51e0\uff1f\u53ea\u56de\u7b54\u4e00\u884c\u3002", expected_contains=weekday_expectations["zh"]),
        SmokeCase("ja-day", "\u4eca\u65e5\u306f\u4f55\u66dc\u65e5\uff1f\u4e00\u884c\u3060\u3051\u3002", expected_contains=weekday_expectations["ja"]),
        SmokeCase("th-day", "\u0e15\u0e2d\u0e19\u0e19\u0e35\u0e49\u0e27\u0e31\u0e19\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46", expected_any_contains=weekday_expectations["th"]),
        SmokeCase(
            "fs-local-id",
            f"tampilkan 3 item pertama dari folder {path_text}",
            expected_any_contains=("\U0001F4C1", "\U0001F4C4"),
        ),
    ]


def build_continuity_smoke_cases(
    *,
    cwd: Path | None = None,
    os_profile: str = "auto",
) -> list[SmokeCase]:
    base_dir = Path(cwd or Path.cwd())
    profile = _normalize_os_profile(os_profile)
    path_text = str(base_dir) if profile == "windows" else base_dir.as_posix()

    return [
        SmokeCase(
            label="continuity-fs-zh",
            prompt=f"tampilkan 3 item pertama dari folder {path_text}",
            followup_prompts=("\u7b2c\u4e8c\u4e2a\u662f\u4ec0\u4e48\uff1f\u7b80\u77ed\u56de\u7b54\u3002",),
            category="continuity",
            expected_any_contains=(".claude",),
            forbidden_contains=(".basetemp", ".dockerignore"),
            expected_continuity_source="answer_reference",
            expected_turn_category="chat",
        ),
        SmokeCase(
            label="continuity-fs-th",
            prompt=f"tampilkan 3 item pertama dari folder {path_text}",
            followup_prompts=("\u0e02\u0e49\u0e2d\u0e17\u0e35\u0e48\u0e2a\u0e2d\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23 \u0e15\u0e2d\u0e1a\u0e2a\u0e31\u0e49\u0e19\u0e46",),
            category="continuity",
            expected_any_contains=(".claude",),
            forbidden_contains=(".basetemp", ".dockerignore"),
            expected_continuity_source="answer_reference",
            expected_turn_category="chat",
        ),
    ]


def build_delivery_smoke_cases(
    *,
    cwd: Path | None = None,
    os_profile: str = "auto",
) -> list[SmokeCase]:
    _normalize_os_profile(os_profile)

    return [
        SmokeCase(
            label="delivery-create-send",
            prompt=(
                "buat file .smoke_tmp/agent_smoke_delivery.txt berisi DELIVERY_SMOKE "
                "lalu kirim ke chat ini. jangan jelaskan, langsung lakukan."
            ),
            category="delivery",
            expected_any_contains=("Message sent to",),
            expected_turn_category="action",
            expected_delivery_verified=True,
        ),
        SmokeCase(
            label="delivery-find-send",
            prompt=(
                "cari file CHANGELOG.md di folder kerja saat ini lalu kirim ke chat ini. "
                "jangan jelaskan, langsung lakukan."
            ),
            category="delivery",
            expected_any_contains=("Message sent to",),
            expected_turn_category="action",
            expected_delivery_verified=True,
        ),
        SmokeCase(
            label="delivery-image-send",
            prompt="generate gambar poster kopi pakai imagen lalu kirim ke chat ini. jangan jelaskan, langsung lakukan.",
            category="delivery",
            expected_any_contains=(
                "Message sent to",
                "isn't available in this runtime yet",
                "Configure a supported image provider first",
            ),
            forbidden_contains=(
                "I couldn't verify delivery because no file attachment was sent",
                "File not found",
            ),
            expected_turn_category="action",
        ),
    ]


def build_memory_smoke_cases() -> list[SmokeCase]:
    return [
        SmokeCase(
            label="memory-followup-id-en",
            prompt="simpan di memory bahwa kode preferensiku MEMID-271. jawab singkat: ok.",
            followup_prompts=("what is my preference code? answer with the code only.",),
            category="memory",
            expected_any_contains=("MEMID-271",),
            expected_turn_category="chat",
        ),
        SmokeCase(
            label="memory-followup-zh-id",
            prompt="请把这条保存到 memory：我的偏好代码是 MEMZH-314。只回答“好”。",
            followup_prompts=("我刚才让你记住的代码是什么？只回答代码。",),
            category="memory",
            expected_any_contains=("MEMZH-314",),
            expected_turn_category="chat",
        ),
        SmokeCase(
            label="memory-followup-th-en",
            prompt="ช่วยจำไว้ว่า รหัสความชอบของฉันคือ MEMTH-808 ตอบสั้นๆว่าโอเค",
            followup_prompts=("what is my preference code? answer with the code only.",),
            category="memory",
            expected_any_contains=("MEMTH-808",),
            expected_turn_category="chat",
        ),
    ]


def build_workflow_smoke_cases() -> list[SmokeCase]:
    return [
        SmokeCase(
            label="workflow-pingpong-upgrade",
            prompt="create a ping pong game web based",
            followup_prompts=("yes continue", "yes continue to upgrade"),
            category="workflow",
            expected_any_contains=("ping-pong", "ping pong", "upgrade"),
            forbidden_contains=("File not found", "/↓", "/↑"),
        ),
    ]


def discover_skill_names(
    *,
    workspace: Path | None = None,
    include_unavailable: bool = False,
) -> list[str]:
    config = load_config()
    target_workspace = Path(workspace or config.workspace_path)
    skills_config = config.skills.model_dump() if hasattr(config.skills, "model_dump") else {}
    loader = SkillsLoader(target_workspace, skills_config=skills_config)
    skills = loader.list_skills(filter_unavailable=not include_unavailable)
    names = sorted({str(item.get("name") or "").strip() for item in skills if str(item.get("name") or "").strip()})
    return names


def build_skill_smoke_cases(
    skill_names: Iterable[str],
    *,
    locales: Iterable[str] = ("en",),
) -> list[SmokeCase]:
    cases: list[SmokeCase] = []
    for skill_name in skill_names:
        normalized_name = str(skill_name or "").strip()
        if not normalized_name:
            continue
        for locale in locales:
            locale_tag = str(locale or "en").strip().lower() or "en"
            label_skill = re.sub(r"[^a-z0-9]+", "-", normalized_name.lower()).strip("-") or "skill"
            cases.append(
                SmokeCase(
                    label=f"skill-{label_skill}-{locale_tag}",
                    prompt=_skill_prompt(locale_tag, normalized_name),
                    category="skill",
                    expected_any_contains=("AI_OK", normalized_name, "skill", "スキル", "技能", "สกิล"),
                )
            )
    return cases


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_repo_pythonpath(env: dict[str, str]) -> dict[str, str]:
    merged = dict(env)
    repo_root = str(_repo_root())
    existing = str(merged.get("PYTHONPATH") or "").strip()
    if existing:
        if repo_root not in existing.split(os.pathsep):
            merged["PYTHONPATH"] = os.pathsep.join([repo_root, existing])
    else:
        merged["PYTHONPATH"] = repo_root
    return merged


def _create_mcp_local_echo_case(
    config_dir: Path,
    *,
    python_executable: str | None = None,
) -> SmokeCase:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "kabot-mcp-local-echo.json"
    config = load_config().model_copy(deep=True)
    config.mcp.enabled = True
    config.mcp.servers["local_echo"] = McpServerConfig(
        transport="stdio",
        command=python_executable or sys.executable,
        args=["-X", "utf8", "-m", "kabot.mcp.dev.echo_server"],
    )
    config_path.write_text(
        json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SmokeCase(
        label="mcp-local-echo",
        prompt="Gunakan tool mcp.local_echo.echo dengan argumen text='halo-mcp-local' lalu tampilkan hasilnya saja.",
        category="mcp",
        expected_any_contains=("halo-mcp-local",),
        env=_with_repo_pythonpath(
            {
                "KABOT_CONFIG": str(config_path),
                "PYTHONIOENCODING": "utf-8",
            }
        ),
    )


def _create_mcp_local_echo_continuity_case(
    config_dir: Path,
    *,
    python_executable: str | None = None,
) -> SmokeCase:
    base_case = _create_mcp_local_echo_case(config_dir, python_executable=python_executable)
    return SmokeCase(
        label="mcp-local-echo-followup",
        prompt="Gunakan tool mcp.local_echo.echo dengan argumen text='halo-mcp-konteks' lalu tampilkan hasilnya saja.",
        followup_prompts=("\u305d\u308c\u3063\u3066\u3069\u3046\u3044\u3046\u610f\u5473\uff1f\u4e00\u884c\u3060\u3051\u3002",),
        category="mcp",
        expected_any_contains=("halo-mcp-konteks",),
        forbidden_contains=("\u305d\u308c\u3063\u3066\u3069\u3046\u3044\u3046\u610f\u5473",),
        expected_continuity_source="answer_reference",
        expected_turn_category="chat",
        env=dict(base_case.env),
    )


def build_agent_command(
    prompt: str,
    *,
    session_id: str,
    python_executable: str | None = None,
) -> list[str]:
    return [
        python_executable or sys.executable,
        "-X",
        "utf8",
        "-m",
        "kabot.cli.commands",
        "agent",
        "-m",
        prompt,
        "--session",
        session_id,
        "--no-markdown",
        "--logs",
    ]


def parse_run_metrics(stderr: str) -> dict[str, Any]:
    route = ""
    continuity_source = ""
    turn_category = ""
    pending_interrupt_count = 0
    completion_artifact_verified = None
    completion_delivery_verified = None
    context_build_ms = None
    first_response_ms = None
    for line in str(stderr or "").splitlines():
        if "Route:" in line:
            route = f"Route: {line.split('Route:', 1)[1].strip()}"
        continuity_match = re.search(r"\bcontinuity_source=([a-z_]+)\b", line)
        if continuity_match:
            continuity_source = str(continuity_match.group(1) or "").strip()
        turn_match = re.search(r"\bturn_category=([a-z_]+)\b", line)
        if turn_match:
            turn_category = str(turn_match.group(1) or "").strip()
        interrupt_match = re.search(r"\bpending_interrupt_count=(\d+)\b", line)
        if interrupt_match:
            pending_interrupt_count = int(interrupt_match.group(1))
        completion_match = re.search(
            r"\bcompletion_evidence\b.*\bartifact_verified=(true|false)\b.*\bdelivery_verified=(true|false)\b",
            line,
        )
        if completion_match:
            completion_artifact_verified = completion_match.group(1) == "true"
            completion_delivery_verified = completion_match.group(2) == "true"
    context_match = re.findall(r"context_build_ms=(\d+)", str(stderr or ""))
    first_match = re.findall(r"first_response_ms=(\d+)", str(stderr or ""))
    if context_match:
        context_build_ms = int(context_match[-1])
    if first_match:
        first_response_ms = int(first_match[-1])
    return {
        "route": route,
        "continuity_source": continuity_source,
        "turn_category": turn_category,
        "pending_interrupt_count": pending_interrupt_count,
        "completion_artifact_verified": completion_artifact_verified,
        "completion_delivery_verified": completion_delivery_verified,
        "context_build_ms": context_build_ms,
        "first_response_ms": first_response_ms,
    }


def _make_session_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(label or "").lower()).strip("-") or "case"
    return f"cli:smoke:{slug}:{int(time.time() * 1000)}"


def run_case(
    case: SmokeCase,
    *,
    cwd: Path | None = None,
    python_executable: str | None = None,
    timeout: int = 120,
) -> SmokeResult:
    session_id = _make_session_id(case.label)
    env = dict(os.environ)
    env.update(case.env or {})
    prompts = [case.prompt, *case.followup_prompts]
    result: subprocess.CompletedProcess[str] | None = None
    combined_stderr: list[str] = []
    combined_stdout: list[str] = []
    for prompt in prompts:
        command = build_agent_command(
            prompt,
            session_id=session_id,
            python_executable=python_executable,
        )
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd or Path.cwd()),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = str(getattr(exc, "stdout", "") or "")
            stderr = str(getattr(exc, "stderr", "") or "")
            metrics = parse_run_metrics(stderr)
            return SmokeResult(
                label=case.label,
                prompt=" -> ".join(prompts),
                session_id=session_id,
                returncode=124,
                stdout=stdout,
                stderr=stderr,
                route=metrics["route"],
                continuity_source=metrics["continuity_source"],
                turn_category=metrics["turn_category"],
                pending_interrupt_count=metrics["pending_interrupt_count"],
                completion_artifact_verified=metrics["completion_artifact_verified"],
                completion_delivery_verified=metrics["completion_delivery_verified"],
                context_build_ms=metrics["context_build_ms"],
                first_response_ms=metrics["first_response_ms"],
                passed=False,
                failure_reason=f"timeout after {timeout}s",
            )
        combined_stderr.append(str(result.stderr or ""))
        combined_stdout.append(str(result.stdout or ""))
        if result.returncode != 0:
            break

    if result is None:
        return SmokeResult(
            label=case.label,
            prompt=" -> ".join(prompts),
            session_id=session_id,
            returncode=1,
            stdout="",
            stderr="",
            passed=False,
            failure_reason="no subprocess result",
        )

    metrics = parse_run_metrics(result.stderr)
    smoke_result = SmokeResult(
        label=case.label,
        prompt=" -> ".join(prompts),
        session_id=session_id,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr="\n".join(part for part in combined_stderr if part),
        route=metrics["route"],
        continuity_source=metrics["continuity_source"],
        turn_category=metrics["turn_category"],
        pending_interrupt_count=metrics["pending_interrupt_count"],
        completion_artifact_verified=metrics["completion_artifact_verified"],
        completion_delivery_verified=metrics["completion_delivery_verified"],
        context_build_ms=metrics["context_build_ms"],
        first_response_ms=metrics["first_response_ms"],
    )
    if result.returncode != 0:
        smoke_result.failure_reason = f"exit={result.returncode}"
        return smoke_result
    if not _stdout_matches_expectations(
        result.stdout,
        expected_contains=case.expected_contains,
    ):
        smoke_result.failure_reason = f"missing expected_contains={case.expected_contains}"
        return smoke_result
    if not _stdout_matches_expectations(
        result.stdout,
        expected_any_contains=case.expected_any_contains,
        forbidden_contains=(),
    ):
        if _stdout_matches_expectations(
            result.stdout,
            expected_any_contains=case.expected_any_contains,
        ):
            smoke_result.failure_reason = f"missing expected_any_contains={case.expected_any_contains}"
        else:
            smoke_result.failure_reason = f"missing expected_any_contains={case.expected_any_contains}"
        return smoke_result
    combined_stdout_text = "\n".join(part for part in combined_stdout if part)
    if case.forbidden_contains and not _stdout_matches_expectations(
        combined_stdout_text,
        expected_any_contains=(),
        forbidden_contains=case.forbidden_contains,
    ):
        smoke_result.failure_reason = f"matched forbidden_contains={case.forbidden_contains}"
        return smoke_result
    expected_continuity_source = str(case.expected_continuity_source or "").strip()
    if expected_continuity_source and smoke_result.continuity_source != expected_continuity_source:
        smoke_result.failure_reason = (
            f"expected continuity_source={expected_continuity_source}, "
            f"got {smoke_result.continuity_source or 'none'}"
        )
        return smoke_result
    expected_turn_category = str(case.expected_turn_category or "").strip()
    if expected_turn_category and smoke_result.turn_category != expected_turn_category:
        smoke_result.failure_reason = (
            f"expected turn_category={expected_turn_category}, "
            f"got {smoke_result.turn_category or 'none'}"
        )
        return smoke_result
    if case.expected_delivery_verified is not None:
        if smoke_result.completion_delivery_verified is not case.expected_delivery_verified:
            smoke_result.failure_reason = (
                f"expected delivery_verified={case.expected_delivery_verified}, "
                f"got {smoke_result.completion_delivery_verified}"
            )
            return smoke_result
    smoke_result.passed = True
    return smoke_result


def apply_thresholds(
    result: SmokeResult,
    *,
    max_context_build_ms: int | None = None,
    max_first_response_ms: int | None = None,
) -> SmokeResult:
    if not result.passed:
        return result

    context_threshold = _normalize_threshold(max_context_build_ms)
    first_threshold = _normalize_threshold(max_first_response_ms)
    failures: list[str] = []

    if context_threshold is not None:
        if result.context_build_ms is None:
            failures.append("missing context_build_ms for threshold gate")
        elif result.context_build_ms > context_threshold:
            failures.append(
                f"context_build_ms={result.context_build_ms} exceeded max_context_build_ms={context_threshold}"
            )

    if first_threshold is not None:
        if result.first_response_ms is None:
            failures.append("missing first_response_ms for threshold gate")
        elif result.first_response_ms > first_threshold:
            failures.append(
                f"first_response_ms={result.first_response_ms} exceeded max_first_response_ms={first_threshold}"
            )

    if failures:
        result.passed = False
        result.failure_reason = "; ".join(failures)

    return result


def _print_human_summary(results: list[SmokeResult]) -> None:
    chunks: list[str] = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        chunks.append(f"[{status}] {result.label}")
        chunks.append(f"  prompt: {result.prompt}")
        chunks.append(f"  session: {result.session_id}")
        chunks.append(f"  route: {result.route}")
        chunks.append(f"  continuity_source: {result.continuity_source}")
        chunks.append(f"  turn_category: {result.turn_category}")
        chunks.append(f"  pending_interrupt_count: {result.pending_interrupt_count}")
        chunks.append(f"  completion_artifact_verified: {result.completion_artifact_verified}")
        chunks.append(f"  completion_delivery_verified: {result.completion_delivery_verified}")
        chunks.append(f"  context_build_ms: {result.context_build_ms}")
        chunks.append(f"  first_response_ms: {result.first_response_ms}")
        if result.failure_reason:
            chunks.append(f"  reason: {result.failure_reason}")
        summary_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()][:4]
        if summary_lines:
            chunks.append(f"  stdout: {' | '.join(summary_lines)}")
        chunks.append("")
    _emit_text("\n".join(chunks))


def serialize_results_json(results: list[SmokeResult]) -> str:
    return json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2)


def _emit_text(text: str) -> None:
    payload = str(text or "")
    if not payload.endswith("\n"):
        payload += "\n"
    try:
        sys.stdout.write(payload)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(payload.encode("utf-8", "replace"))
        sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run multilingual Kabot agent smoke cases.")
    parser.add_argument("--cwd", default=None, help="Working directory for subprocess runs.")
    parser.add_argument("--os-profile", default="auto", choices=["auto", "windows", "posix"])
    parser.add_argument("--python", default=sys.executable, help="Python executable to use.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json", action="store_true", help="Print results as JSON.")
    parser.add_argument("--no-default-cases", action="store_true", help="Skip built-in temporal/filesystem smoke cases.")
    parser.add_argument(
        "--continuity-cases",
        action="store_true",
        help="Add multilingual multi-turn continuity smoke cases.",
    )
    parser.add_argument(
        "--delivery-cases",
        action="store_true",
        help="Add artifact delivery smoke cases (create/find/generate then send).",
    )
    parser.add_argument(
        "--memory-cases",
        action="store_true",
        help="Add multilingual memory-backed follow-up smoke cases.",
    )
    parser.add_argument(
        "--workflow-cases",
        action="store_true",
        help="Add multi-turn workflow regression cases (for example create -> continue -> upgrade).",
    )
    parser.add_argument("--skill", action="append", default=[], help="Add explicit-skill smoke case(s).")
    parser.add_argument("--all-skills", action="store_true", help="Discover all skills and add explicit-skill smoke cases.")
    parser.add_argument("--mcp-local-echo", action="store_true", help="Add a local Python MCP echo smoke case.")
    parser.add_argument(
        "--max-context-build-ms",
        type=int,
        default=None,
        help="Fail passing cases whose context_build_ms exceeds this threshold.",
    )
    parser.add_argument(
        "--max-first-response-ms",
        type=int,
        default=None,
        help="Fail passing cases whose first_response_ms exceeds this threshold.",
    )
    parser.add_argument(
        "--skill-locales",
        default="en",
        help="Comma-separated locales for explicit-skill smoke prompts (e.g. en,id,zh,ja,th).",
    )
    args = parser.parse_args(argv)

    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    with tempfile.TemporaryDirectory(prefix="kabot-mcp-smoke-") as temp_dir_name:
        cases: list[SmokeCase] = []
        if not args.no_default_cases:
            cases.extend(build_smoke_cases(cwd=cwd, os_profile=args.os_profile))
        if args.continuity_cases:
            cases.extend(build_continuity_smoke_cases(cwd=cwd, os_profile=args.os_profile))
        if args.delivery_cases:
            cases.extend(build_delivery_smoke_cases(cwd=cwd, os_profile=args.os_profile))
        if args.memory_cases:
            cases.extend(build_memory_smoke_cases())
        if args.workflow_cases:
            cases.extend(build_workflow_smoke_cases())

        skill_names: list[str] = [str(item).strip() for item in args.skill if str(item).strip()]
        if args.all_skills:
            skill_names.extend(discover_skill_names(workspace=cwd, include_unavailable=False))
        unique_skill_names = sorted({name for name in skill_names if name})
        locales = [part.strip().lower() for part in str(args.skill_locales or "en").split(",") if part.strip()]
        if unique_skill_names:
            cases.extend(build_skill_smoke_cases(unique_skill_names, locales=locales or ("en",)))
        if args.mcp_local_echo:
            cases.append(
                _create_mcp_local_echo_case(
                    Path(temp_dir_name),
                    python_executable=args.python,
                )
            )
            if args.continuity_cases:
                cases.append(
                    _create_mcp_local_echo_continuity_case(
                        Path(temp_dir_name),
                        python_executable=args.python,
                    )
                )

        results = [
            apply_thresholds(
                run_case(case, cwd=cwd, python_executable=args.python, timeout=args.timeout),
                max_context_build_ms=args.max_context_build_ms,
                max_first_response_ms=args.max_first_response_ms,
            )
            for case in cases
        ]
    if args.json:
        _emit_text(serialize_results_json(results))
    else:
        _print_human_summary(results)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
