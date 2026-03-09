"""Cross-platform smoke matrix runner for `kabot agent`."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from kabot.agent.skills import SkillsLoader
from kabot.config.loader import load_config


@dataclass(frozen=True)
class SmokeCase:
    label: str
    prompt: str
    category: str = "default"
    expected_contains: tuple[str, ...] = ()
    expected_any_contains: tuple[str, ...] = ()


@dataclass
class SmokeResult:
    label: str
    prompt: str
    session_id: str
    returncode: int
    stdout: str
    stderr: str
    route: str = ""
    context_build_ms: int | None = None
    first_response_ms: int | None = None
    passed: bool = False
    failure_reason: str = ""


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
        "zh": f"请用 {skill_name} 技能处理这个请求。",
        "ja": f"{skill_name} スキルを使ってこの依頼を手伝って。",
        "th": f"ช่วยใช้สกิล {skill_name} กับงานนี้หน่อย",
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

    return [
        SmokeCase("id-day", "hari apa sekarang? jawab singkat, pakai WIB ya.", expected_contains=("Senin",)),
        SmokeCase("id-weird-day", "bro sekarang hari apa sih woi, jawab satu baris", expected_contains=("Senin",)),
        SmokeCase("zh-day", "今天星期几？只回答一行。", expected_contains=("星期一",)),
        SmokeCase("ja-day", "今日は何曜日？一行だけ。", expected_contains=("月曜日",)),
        SmokeCase("th-day", "ตอนนี้วันอะไร ตอบสั้นๆ", expected_any_contains=("วันจันทร์", "จันทร์")),
        SmokeCase(
            "fs-local-id",
            f"tampilkan 3 item pertama dari folder {path_text}",
            expected_any_contains=("📁", "📄"),
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
    context_build_ms = None
    first_response_ms = None
    for line in str(stderr or "").splitlines():
        if "Route:" in line:
            route = f"Route: {line.split('Route:', 1)[1].strip()}"
    context_match = re.findall(r"context_build_ms=(\d+)", str(stderr or ""))
    first_match = re.findall(r"first_response_ms=(\d+)", str(stderr or ""))
    if context_match:
        context_build_ms = int(context_match[-1])
    if first_match:
        first_response_ms = int(first_match[-1])
    return {
        "route": route,
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
    command = build_agent_command(case.prompt, session_id=session_id, python_executable=python_executable)
    result = subprocess.run(
        command,
        cwd=str(cwd or Path.cwd()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    metrics = parse_run_metrics(result.stderr)
    smoke_result = SmokeResult(
        label=case.label,
        prompt=case.prompt,
        session_id=session_id,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        route=metrics["route"],
        context_build_ms=metrics["context_build_ms"],
        first_response_ms=metrics["first_response_ms"],
    )
    if result.returncode != 0:
        smoke_result.failure_reason = f"exit={result.returncode}"
        return smoke_result
    if case.expected_contains and not all(expected in result.stdout for expected in case.expected_contains):
        smoke_result.failure_reason = f"missing expected_contains={case.expected_contains}"
        return smoke_result
    if case.expected_any_contains and not any(expected in result.stdout for expected in case.expected_any_contains):
        smoke_result.failure_reason = f"missing expected_any_contains={case.expected_any_contains}"
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
    parser.add_argument("--skill", action="append", default=[], help="Add explicit-skill smoke case(s).")
    parser.add_argument("--all-skills", action="store_true", help="Discover all skills and add explicit-skill smoke cases.")
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
    cases: list[SmokeCase] = []
    if not args.no_default_cases:
        cases.extend(build_smoke_cases(cwd=cwd, os_profile=args.os_profile))

    skill_names: list[str] = [str(item).strip() for item in args.skill if str(item).strip()]
    if args.all_skills:
        skill_names.extend(discover_skill_names(workspace=cwd, include_unavailable=False))
    unique_skill_names = sorted({name for name in skill_names if name})
    locales = [part.strip().lower() for part in str(args.skill_locales or "en").split(",") if part.strip()]
    if unique_skill_names:
        cases.extend(build_skill_smoke_cases(unique_skill_names, locales=locales or ("en",)))

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
