"""Skills loader for agent capabilities."""

import hashlib
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from kabot.agent.tools.stock_matching import extract_crypto_ids, extract_stock_symbols
from kabot.agent.skills_matching import (
    BUILTIN_SKILLS_DIR,
    WORKFLOW_CHAINS,
    _extract_keywords,
    _intent_alias_bonus,
    _naive_stem,
    looks_like_skill_catalog_request,
    looks_like_skill_creation_request,
    looks_like_skill_install_request,
    normalize_skill_reference_name,
)
from kabot.agent.skills_parts.runtime import (
    get_always_skills as runtime_get_always_skills,
)
from kabot.agent.skills_parts.runtime import (
    get_skill_metadata_from_file as runtime_get_skill_metadata_from_file,
)
from kabot.agent.skills_parts.runtime import (
    get_skill_status as runtime_get_skill_status,
)
from kabot.agent.skills_parts.runtime import (
    iter_skill_roots_with_source as runtime_iter_skill_roots_with_source,
)
from kabot.agent.skills_parts.runtime import (
    iter_unique_skill_candidates as runtime_iter_unique_skill_candidates,
)
from kabot.agent.skills_parts.runtime import (
    match_explicit_skill_fast_path as runtime_match_explicit_skill_fast_path,
)
from kabot.agent.skills_parts.runtime import (
    parse_frontmatter_metadata as runtime_parse_frontmatter_metadata,
)
from kabot.config.skills_settings import (
    get_skills_entries,
    normalize_skills_settings,
    resolve_allow_bundled,
    resolve_install_settings,
    resolve_load_settings,
)
from kabot.utils.skill_validator import validate_skill

logger = logging.getLogger(__name__)

_LEGACY_EXTERNAL_METADATA_KEY = "".join(
    chr(code) for code in (111, 112, 101, 110, 99, 108, 97, 119)
)

_FINANCE_SKILL_MARKERS = {
    "stock",
    "stocks",
    "saham",
    "crypto",
    "market",
    "markets",
    "ticker",
    "tickers",
    "quote",
    "quotes",
    "finance",
    "trading",
    "watchlist",
    "analysis",
}
_STOCK_DOMAIN_MARKERS = {
    "stock",
    "stocks",
    "saham",
    "equity",
    "equities",
    "ihsg",
    "idx",
}
_CRYPTO_DOMAIN_MARKERS = {
    "crypto",
    "bitcoin",
    "ethereum",
    "binance",
    "coin",
    "coins",
    "token",
    "tokens",
    "wallet",
    "blockchain",
    "futures",
    "defi",
}
_GENERIC_FINANCE_DOMAIN_MARKERS = {
    "market",
    "markets",
    "ticker",
    "tickers",
    "quote",
    "quotes",
    "finance",
    "trading",
    "watchlist",
    "analysis",
}
_FINANCE_QUERY_MARKERS = (
    "stock",
    "saham",
    "crypto",
    "btc",
    "eth",
    "harga",
    "price",
    "ticker",
    "market",
    "quote",
    "ihsg",
    "idx",
)

_TRUEISH_FRONTMATTER_VALUES = {"1", "true", "yes", "on"}
_FALSEISH_FRONTMATTER_VALUES = {"0", "false", "no", "off"}

__all__ = [
    "BUILTIN_SKILLS_DIR",
    "SkillsLoader",
    "WORKFLOW_CHAINS",
    "_extract_keywords",
    "_intent_alias_bonus",
    "_naive_stem",
    "looks_like_skill_catalog_request",
    "looks_like_skill_creation_request",
    "looks_like_skill_install_request",
    "normalize_skill_reference_name",
]


def _looks_like_finance_request(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    try:
        if extract_stock_symbols(text):
            return True
    except Exception:
        pass
    try:
        if extract_crypto_ids(text):
            return True
    except Exception:
        pass
    return any(marker in normalized for marker in _FINANCE_QUERY_MARKERS)


def _is_finance_skill_candidate(skill_name: str, description: str) -> bool:
    haystack = f"{skill_name} {description}".strip().lower()
    if not haystack:
        return False
    return any(marker in haystack for marker in _FINANCE_SKILL_MARKERS)


def _classify_finance_request(text: str) -> str | None:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return None
    has_stock = any(marker in normalized for marker in _STOCK_DOMAIN_MARKERS)
    has_crypto = any(marker in normalized for marker in _CRYPTO_DOMAIN_MARKERS)
    try:
        if extract_stock_symbols(text):
            has_stock = True
    except Exception:
        pass
    try:
        if extract_crypto_ids(text):
            has_crypto = True
    except Exception:
        pass
    if has_stock and has_crypto:
        return "mixed"
    if has_stock:
        return "stock"
    if has_crypto:
        return "crypto"
    if any(marker in normalized for marker in _GENERIC_FINANCE_DOMAIN_MARKERS):
        return "generic"
    if _looks_like_finance_request(text):
        return "generic"
    return None


def _classify_finance_skill(skill_name: str, description: str) -> str | None:
    haystack = f"{skill_name} {description}".strip().lower()
    if not haystack:
        return None
    has_stock = any(marker in haystack for marker in _STOCK_DOMAIN_MARKERS)
    has_crypto = any(marker in haystack for marker in _CRYPTO_DOMAIN_MARKERS)
    has_generic = any(marker in haystack for marker in _GENERIC_FINANCE_DOMAIN_MARKERS)
    if has_stock and has_crypto:
        return "mixed"
    if has_stock:
        return "stock"
    if has_crypto:
        return "crypto"
    if has_generic or _is_finance_skill_candidate(skill_name, description):
        return "generic"
    return None


def _finance_skill_matches_request(skill_name: str, description: str, text: str) -> bool:
    request_kind = _classify_finance_request(text)
    skill_kind = _classify_finance_skill(skill_name, description)
    if not request_kind or not skill_kind:
        return False
    if request_kind == "mixed" or skill_kind == "mixed":
        return True
    if request_kind == "generic" or skill_kind == "generic":
        return True
    return request_kind == skill_kind


def _coerce_frontmatter_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in _TRUEISH_FRONTMATTER_VALUES:
        return True
    if normalized in _FALSEISH_FRONTMATTER_VALUES:
        return False
    return default

class SkillsLoader:
    """
    Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.
    """

    def __init__(
        self,
        workspace: Path,
        builtin_skills_dir: Path | None = None,
        skills_config: dict | None = None,
    ):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.project_agents_skills = workspace / ".agents" / "skills"
        self.personal_agents_skills = Path.home() / ".agents" / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
        self._skills_config = normalize_skills_settings(skills_config or {})
        load_settings = resolve_load_settings(self._skills_config)
        self._install_settings = resolve_install_settings(self._skills_config)
        managed_dir = load_settings.get("managed_dir")
        if isinstance(managed_dir, str) and managed_dir.strip():
            self.managed_skills: Path | None = Path(managed_dir).expanduser()
        else:
            # Global shared skills source (default).
            self.managed_skills = Path.home() / ".kabot" / "skills"

        extra_dirs = load_settings.get("extra_dirs", [])
        self.extra_skill_dirs: list[Path] = []
        if isinstance(extra_dirs, list):
            for raw in extra_dirs:
                path_str = str(raw).strip()
                if path_str:
                    self.extra_skill_dirs.append(Path(path_str).expanduser())

        self._allow_bundled = set(resolve_allow_bundled(self._skills_config))
        self._skill_entries = get_skills_entries(self._skills_config)
        self._skill_index: dict[str, set[str]] | None = None  # lazy cache
        self._body_index: dict[str, set[str]] | None = None   # lazy cache
        self._index_snapshot: tuple[tuple[str, int, int], ...] | None = None
        self._list_cache_ttl_seconds = 60.0
        self._list_skills_cache: dict[bool, tuple[float, tuple[tuple[str, int, int, int], ...], list[dict[str, Any]]]] = {}
        self._summary_cache: tuple[float, tuple[tuple[str, int, int, int], ...], str] | None = None
        self._always_skills_cache: tuple[float, tuple[tuple[str, int, int, int], ...], list[str]] | None = None

    def _build_skill_index(self) -> dict[str, set[str]]:
        """Build keyword index from all skill descriptions (cached)."""
        current_snapshot = self._compute_skill_snapshot()
        if self._skill_index is not None and self._index_snapshot == current_snapshot:
            return self._skill_index

        index: dict[str, set[str]] = {}
        body_index: dict[str, set[str]] = {}
        for skill in self.list_skills(filter_unavailable=False):
            if bool(skill.get("disable_model_invocation")):
                continue
            desc = self._get_skill_description(skill["name"])
            # Primary keywords: from description + skill name (high signal)
            keywords = _extract_keywords(desc)
            keywords.update(_extract_keywords(skill["name"].replace("-", " ").replace("_", " ")))
            index[skill["name"]] = keywords
            # Secondary keywords: from body content (lower signal, more noise)
            content = self.load_skill(skill["name"])
            if content:
                body = self._strip_frontmatter(content)[:500]
                body_kw = _extract_keywords(body)
                body_index[skill["name"]] = {kw for kw in body_kw if len(kw) >= 4} - keywords
            else:
                body_index[skill["name"]] = set()

        self._skill_index = index
        self._body_index = body_index
        self._index_snapshot = current_snapshot
        return index

    def _iter_skill_roots(self) -> list[Path]:
        roots: list[Path] = []
        roots.extend([
            self.workspace_skills,
            self.project_agents_skills,
            self.personal_agents_skills,
        ])
        if self.managed_skills:
            roots.append(self.managed_skills)
        if self.builtin_skills:
            roots.append(self.builtin_skills)
        roots.extend(self.extra_skill_dirs)
        return roots

    def _iter_skill_roots_with_source(self) -> list[tuple[Path, str]]:
        return runtime_iter_skill_roots_with_source(self)

    def _iter_unique_skill_candidates(self):
        return runtime_iter_unique_skill_candidates(self)

    def _iter_skill_files(self) -> list[Path]:
        files: list[Path] = []
        for root in self._iter_skill_roots():
            if not root.exists():
                continue
            for skill_dir in root.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    files.append(skill_file)
        return files

    def _compute_skill_snapshot(self) -> tuple[tuple[str, int, int], ...]:
        """Return deterministic snapshot of skill files for cache invalidation."""
        snapshot: list[tuple[str, int, int]] = []
        for skill_file in self._iter_skill_files():
            try:
                stat = skill_file.stat()
            except OSError:
                continue
            snapshot.append((str(skill_file), int(stat.st_mtime_ns), int(stat.st_size)))
        snapshot.sort(key=lambda item: item[0])
        return tuple(snapshot)

    def _compute_roots_snapshot(self) -> tuple[tuple[str, int, int, int], ...]:
        """Cheap snapshot for list/summary cache invalidation based on root directories."""
        snapshot: list[tuple[str, int, int, int]] = []
        for root in self._iter_skill_roots():
            exists = root.exists()
            if not exists:
                snapshot.append((str(root), 0, 0, 0))
                continue
            try:
                stat = root.stat()
                # include child dir count so cache invalidates when skills are added/removed
                child_count = sum(1 for p in root.iterdir() if p.is_dir())
                snapshot.append((str(root), 1, int(stat.st_mtime_ns), int(child_count)))
            except OSError:
                snapshot.append((str(root), 1, 0, 0))
        env_pairs = [f"{key}={value}" for key, value in sorted(os.environ.items())]
        env_blob = "\0".join(env_pairs).encode("utf-8", errors="ignore")
        env_digest = hashlib.sha1(env_blob).hexdigest()
        snapshot.append(
            (
                "__env__",
                int(env_digest[:12], 16),
                len(env_pairs),
                len(os.environ.get("PATH", "")),
            )
        )
        snapshot.sort(key=lambda item: item[0])
        return tuple(snapshot)

    def match_skills(self, message: str, profile: str = "GENERAL",
                     max_results: int = 3) -> list[str]:
        """
        Auto-select relevant skills based on user message content.

        Scores each skill by keyword overlap between the message and the
        skill's description. Applies workflow chain expansion for related skills.

        Args:
            message: User message text.
            profile: Router profile (CODING, CHAT, RESEARCH, GENERAL).
            max_results: Maximum number of skills to return.

        Returns:
            List of skill names, sorted by relevance score (best first).
        """
        if not message or len(message.strip()) < 5:
            return []

        message_lower = message.lower()
        explicit_fast_matches = self._match_explicit_skill_fast_path(
            message=message,
            message_lower=message_lower,
            max_results=max_results,
        )
        if explicit_fast_matches is not None:
            return explicit_fast_matches

        index = self._build_skill_index()
        msg_keywords = _extract_keywords(message)
        finance_request = _looks_like_finance_request(message_lower)

        if not msg_keywords:
            if not finance_request:
                return []

        # Score each skill
        body_idx = self._body_index or {}
        scored: list[tuple[str, bool, float]] = []
        for skill_name, skill_keywords in index.items():
            if not skill_keywords:
                continue

            # Primary overlap: description + name keywords (high signal)
            overlap = msg_keywords & skill_keywords
            # Secondary overlap: body keywords (low signal)
            body_keywords = body_idx.get(skill_name, set())
            body_overlap = msg_keywords & body_keywords

            # Extra multilingual signal: allow non-ASCII keyword containment
            # (helps languages where user text may omit spaces, e.g. Thai).
            contain_overlap = {
                kw for kw in skill_keywords
                if len(kw) >= 2 and any(ord(ch) > 127 for ch in kw) and kw in message_lower
            }
            contain_body_overlap = {
                kw for kw in body_keywords
                if len(kw) >= 2 and any(ord(ch) > 127 for ch in kw) and kw in message_lower
            }
            alias_bonus = _intent_alias_bonus(skill_name, message_lower)
            finance_skill_match = _finance_skill_matches_request(
                skill_name,
                self._get_skill_description(skill_name),
                message,
            )

            if (
                not overlap
                and not body_overlap
                and not contain_overlap
                and not contain_body_overlap
                and alias_bonus <= 0
                and not finance_skill_match
            ):
                continue

            # Primary keywords score 1.0 each, body keywords 0.2 each
            score = len(overlap) + 0.2 * len(body_overlap)
            score += 0.8 * len(contain_overlap) + 0.2 * len(contain_body_overlap)
            if finance_skill_match:
                score += 2.5

            # Strong bonus: exact skill name match (e.g., user says "spotify" or "discord")
            name_words = set(skill_name.replace("-", " ").split())
            # Also check stemmed name words (e.g., "debugging" → "debug")
            stemmed_name = {_naive_stem(w) for w in name_words}
            stemmed_msg = {_naive_stem(w) for w in msg_keywords}
            name_overlap = (name_words & msg_keywords) | (stemmed_name & stemmed_msg)
            if name_overlap:
                score += 2.0 * len(name_overlap)

            # Strongest signal: user explicitly references full skill name.
            explicit_full_name_match = bool(
                re.search(rf"(?<![\w-]){re.escape(skill_name.lower())}(?![\w-])", message_lower)
            )
            if explicit_full_name_match:
                score += 5.0
            if alias_bonus > 0:
                score += alias_bonus

            # Bonus for action/domain word overlap (verbs that indicate intent)
            action_words = {"debug", "fix", "error", "bug", "test", "create", "build",
                            "search", "find", "send", "play", "download", "upload",
                            "read", "write", "edit", "delete", "check", "control",
                            "summarize", "transcribe", "generate", "manage", "schedule",
                            "deploy", "install", "configure", "monitor", "order", "capture"}
            all_overlap = overlap | body_overlap | contain_overlap | contain_body_overlap
            action_overlap = all_overlap & action_words
            if action_overlap:
                score += 0.3 * len(action_overlap)

            # Skip weak matches: require 2+ overlaps unless name matches
            total_overlap = len(overlap) + len(body_overlap) + len(contain_overlap) + len(contain_body_overlap)
            if (
                alias_bonus <= 0
                and not explicit_full_name_match
                and not name_overlap
                and not finance_skill_match
                and total_overlap < 2
            ):
                continue

            scored.append((skill_name, explicit_full_name_match, score))

        # Sort by explicit full-name match first, then score descending.
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)

        # Take top N
        selected = [name for name, _, _ in scored[:max_results]]

        # Expand workflow chains
        expanded: list[str] = []
        for skill_name in selected:
            if skill_name not in expanded:
                expanded.append(skill_name)
            for chain_skill in WORKFLOW_CHAINS.get(skill_name, []):
                if chain_skill not in expanded and len(expanded) < max_results + 2:
                    expanded.append(chain_skill)

        # Validate requirements for selected skills
        validated = []
        for skill_name in expanded:
            status = self._get_skill_status(skill_name)
            if status and status.get("eligible"):
                validated.append(skill_name)
            else:
                missing = self._format_skill_unavailability(status) if status else "requirements not met"
                install_options = (status or {}).get("install", [])
                install_cmd = ""
                if isinstance(install_options, list) and install_options:
                    first_option = install_options[0] if isinstance(install_options[0], dict) else {}
                    install_cmd = (
                        str(first_option.get("label", "")).strip()
                        or str(first_option.get("cmd", "")).strip()
                    )
                hint = f"[SKILL_UNAVAILABLE] {skill_name} needs: {missing}"
                if install_cmd:
                    hint += f" (install: {install_cmd})"
                from loguru import logger
                logger.info(hint)
                # Still include the skill name but mark it
                validated.append(f"{skill_name} [NEEDS: {missing}]")

        return validated[:max_results + 2]  # Allow up to 5 with chains

    def match_skill_details(
        self,
        message: str,
        profile: str = "GENERAL",
        max_results: int = 3,
        *,
        filter_unavailable: bool = False,
    ) -> list[dict[str, Any]]:
        """Return matched skills enriched with source and eligibility metadata."""
        matched_names = self.match_skills(message, profile=profile, max_results=max_results)
        if not matched_names:
            return []

        statuses = {
            normalize_skill_reference_name(str(item.get("name") or "")): item
            for item in self.list_skills(filter_unavailable=filter_unavailable)
        }
        details: list[dict[str, Any]] = []
        for raw_name in matched_names:
            normalized = normalize_skill_reference_name(raw_name)
            if not normalized:
                continue
            status = statuses.get(normalized)
            if isinstance(status, dict):
                details.append(dict(status))
        return details

    def has_preferred_external_skill_match(
        self,
        message: str,
        profile: str = "GENERAL",
        max_results: int = 3,
    ) -> bool:
        """
        Return True when an eligible non-builtin skill matches this request.

        Built-in stock/crypto tools stay available as fallback, but external
        skills should win when they clearly match the query.
        """
        for detail in self.match_skill_details(
            message,
            profile=profile,
            max_results=max_results,
            filter_unavailable=False,
        ):
            if not bool(detail.get("eligible")):
                continue
            source = str(detail.get("source") or "").strip().lower()
            if source and source != "builtin":
                return True
        return False

    def has_external_finance_skill_available(self) -> bool:
        """Return True when any non-builtin finance skill is installed."""
        for detail in self.list_skills(filter_unavailable=False):
            source = str(detail.get("source") or "").strip().lower()
            if not source or source == "builtin":
                continue
            if _is_finance_skill_candidate(
                str(detail.get("name") or ""),
                str(detail.get("description") or ""),
            ):
                return True
        return False

    def should_prefer_external_finance_skill(
        self,
        message: str,
        profile: str = "GENERAL",
    ) -> bool:
        """
        Return True when finance/crypto requests should stay on the external-skill lane.

        This keeps legacy built-in finance tools archived behind workspace/managed
        skill packs, which is closer to Kabot's current skill-first model.
        """
        if not self.has_external_finance_skill_available():
            return False
        for detail in self.match_skill_details(
            message,
            profile=profile,
            max_results=3,
            filter_unavailable=False,
        ):
            source = str(detail.get("source") or "").strip().lower()
            if not source or source == "builtin":
                continue
            if _finance_skill_matches_request(
                str(detail.get("name") or ""),
                str(detail.get("description") or ""),
                message,
            ):
                return True
        if self.has_preferred_external_skill_match(message, profile=profile):
            return True
        return False

    def _match_explicit_skill_fast_path(
        self,
        *,
        message: str,
        message_lower: str,
        max_results: int,
    ) -> list[str] | None:
        return runtime_match_explicit_skill_fast_path(
            self,
            message=message,
            message_lower=message_lower,
            max_results=max_results,
        )

    def _resolve_node_install_command(self, package_name: str) -> str:
        manager = str(self._install_settings.get("node_manager") or "npm").strip().lower()
        if manager == "pnpm":
            return f"pnpm add -g {package_name}"
        if manager == "yarn":
            return f"yarn global add {package_name}"
        if manager == "bun":
            return f"bun add -g {package_name}"
        return f"npm install -g {package_name}"

    def _is_installer_supported_on_current_os(self, spec: dict) -> bool:
        os_targets = spec.get("os") or []
        if not isinstance(os_targets, list) or not os_targets:
            return True
        import sys

        aliases = self._platform_aliases(sys.platform)
        for target in os_targets:
            normalized = str(target).strip().lower()
            if normalized in aliases:
                return True
        return False

    def _normalize_single_install_spec(self, raw: Any, index: int = 0) -> dict | None:
        if isinstance(raw, str):
            cmd = raw.strip()
            if not cmd:
                return None
            return {
                "id": f"cmd-{index}",
                "kind": "cmd",
                "label": f"Run: {cmd}",
                "cmd": cmd,
                "bins": [],
                "os": [],
            }

        if not isinstance(raw, dict):
            return None

        spec = dict(raw)
        # Legacy format: {"cmd": "..."}.
        if "kind" not in spec and str(spec.get("cmd") or "").strip():
            cmd = str(spec.get("cmd") or "").strip()
            label = str(spec.get("label") or "").strip() or f"Run: {cmd}"
            bins = spec.get("bins") if isinstance(spec.get("bins"), list) else []
            os_list = spec.get("os") if isinstance(spec.get("os"), list) else []
            return {
                "id": str(spec.get("id") or f"cmd-{index}").strip() or f"cmd-{index}",
                "kind": "cmd",
                "label": label,
                "cmd": cmd,
                "bins": [str(b).strip() for b in bins if str(b).strip()],
                "os": [str(v).strip().lower() for v in os_list if str(v).strip()],
            }

        kind = str(spec.get("kind") or "").strip().lower()
        if kind not in {"brew", "node", "go", "uv", "download", "cmd"}:
            return None

        normalized: dict[str, Any] = {
            "id": str(spec.get("id") or f"{kind}-{index}").strip() or f"{kind}-{index}",
            "kind": kind,
            "label": str(spec.get("label") or "").strip(),
            "bins": [],
            "os": [],
        }
        bins = spec.get("bins") if isinstance(spec.get("bins"), list) else []
        normalized["bins"] = [str(b).strip() for b in bins if str(b).strip()]
        os_list = spec.get("os") if isinstance(spec.get("os"), list) else []
        normalized["os"] = [str(v).strip().lower() for v in os_list if str(v).strip()]

        if kind == "brew":
            formula = str(spec.get("formula") or "").strip()
            if formula:
                normalized["formula"] = formula
                if not normalized["label"]:
                    normalized["label"] = f"Install {formula} (brew)"
                normalized["cmd"] = f"brew install {formula}"
        elif kind == "node":
            package = str(spec.get("package") or "").strip()
            if package:
                normalized["package"] = package
                if not normalized["label"]:
                    normalized["label"] = f"Install {package} ({self._install_settings.get('node_manager', 'npm')})"
                normalized["cmd"] = self._resolve_node_install_command(package)
        elif kind == "go":
            module = str(spec.get("module") or "").strip()
            if module:
                normalized["module"] = module
                if not normalized["label"]:
                    normalized["label"] = f"Install {module} (go)"
                normalized["cmd"] = f"go install {module}"
        elif kind == "uv":
            package = str(spec.get("package") or "").strip()
            if package:
                normalized["package"] = package
                if not normalized["label"]:
                    normalized["label"] = f"Install {package} (uv)"
                normalized["cmd"] = f"uv tool install {package}"
        elif kind == "download":
            url = str(spec.get("url") or "").strip()
            if url:
                normalized["url"] = url
                if not normalized["label"]:
                    normalized["label"] = f"Download: {url}"
                normalized["cmd"] = f"Download manually: {url}"
        elif kind == "cmd":
            cmd = str(spec.get("cmd") or "").strip()
            if cmd:
                normalized["cmd"] = cmd
                if not normalized["label"]:
                    normalized["label"] = f"Run: {cmd}"

        if not normalized.get("cmd") and kind != "download":
            return None
        return normalized

    def _normalize_install_specs(self, install_meta: Any) -> list[dict]:
        raw_specs: list[Any]
        if isinstance(install_meta, list):
            raw_specs = install_meta
        elif install_meta:
            raw_specs = [install_meta]
        else:
            raw_specs = []

        specs: list[dict] = []
        for index, raw in enumerate(raw_specs):
            spec = self._normalize_single_install_spec(raw, index=index)
            if not spec:
                continue
            if not self._is_installer_supported_on_current_os(spec):
                continue
            specs.append(spec)

        def _priority(s: dict) -> tuple[int, str]:
            kind = str(s.get("kind") or "")
            if kind == "uv":
                rank = 0
            elif kind == "node":
                rank = 1
            elif kind == "brew":
                rank = 2 if bool(self._install_settings.get("prefer_brew", True)) else 4
            elif kind == "go":
                rank = 3
            elif kind == "download":
                rank = 5
            else:
                rank = 6
            return rank, str(s.get("id") or "")

        specs.sort(key=_priority)
        return specs

    def list_skills(self, filter_unavailable: bool = True) -> list[dict]:
        """
        List all available skills with detailed status.

        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.

        Returns:
            List of skill info dicts with 'name', 'path', 'source', 'valid',
            'eligible', 'missing' (bins, env), 'install', 'description'.
        """
        roots_snapshot = self._compute_roots_snapshot()
        now = time.time()
        cached = self._list_skills_cache.get(bool(filter_unavailable))
        if cached:
            cached_at, cached_snapshot, cached_items = cached
            if cached_snapshot == roots_snapshot and (now - cached_at) <= self._list_cache_ttl_seconds:
                # Return shallow copies so callers cannot mutate cache in place.
                return [dict(item) for item in cached_items]

        skills = []
        seen_names = set()

        def _process_skill(name, path, source, valid):
            if name in seen_names:
                return
            seen_names.add(name)

            frontmatter = self.get_skill_metadata(name) or {}
            meta = self._get_skill_meta(name)
            invocation_policy = self._resolve_skill_invocation_policy(frontmatter)
            install_specs = self._normalize_install_specs(meta.get("install", {}))
            desc = self._get_skill_description(name)
            skill_key = str(meta.get("skillKey") or name).strip() or name
            skill_cfg = self._skill_entries.get(skill_key, {})
            if not isinstance(skill_cfg, dict):
                skill_cfg = {}
            disabled = skill_cfg.get("enabled") is False
            blocked_by_allowlist = (
                source == "builtin"
                and len(self._allow_bundled) > 0
                and name not in self._allow_bundled
                and skill_key not in self._allow_bundled
            )

            # Check requirements
            missing_bins = []
            missing_env = []
            requires = meta.get("requires", {})
            entry_env = skill_cfg.get("env", {})
            if not isinstance(entry_env, dict):
                entry_env = {}
            entry_api_key = str(skill_cfg.get("api_key") or "").strip()

            for b in requires.get("bins", []):
                if not shutil.which(b):
                    missing_bins.append(b)

            primary_env = meta.get("primaryEnv")
            for e in requires.get("env", []):
                env_name = str(e).strip()
                if not env_name:
                    continue
                env_satisfied = bool(os.environ.get(env_name))
                if not env_satisfied and entry_env.get(env_name):
                    env_satisfied = True
                if not env_satisfied and entry_api_key and primary_env == env_name:
                    env_satisfied = True
                if not env_satisfied:
                    missing_env.append(env_name)

            # Check OS support (metadata.os preferred, requires.os legacy fallback).
            unsupported_os = self._missing_os(meta)

            eligible = (
                len(missing_bins) == 0
                and len(missing_env) == 0
                and len(unsupported_os) == 0
                and not disabled
                and not blocked_by_allowlist
            )

            # primaryEnv logic: explicit meta > first missing env > first required env
            if not primary_env and missing_env:
                primary_env = missing_env[0]
            if not primary_env and requires.get("env"):
                 primary_env = requires.get("env")[0]

            skill_info = {
                "name": name,
                "skill_key": skill_key,
                "path": str(path),
                "source": source,
                "valid": valid,
                "eligible": eligible,
                "disabled": disabled,
                "blocked_by_allowlist": blocked_by_allowlist,
                "primaryEnv": primary_env,
                "missing": {
                    "bins": missing_bins,
                    "env": missing_env,
                    "os": unsupported_os
                },
                "install": install_specs,
                "description": desc,
                "user_invocable": bool(invocation_policy.get("user_invocable", True)),
                "disable_model_invocation": bool(
                    invocation_policy.get("disable_model_invocation", False)
                ),
                "command_dispatch": str(invocation_policy.get("command_dispatch") or "").strip(),
                "command_tool": str(invocation_policy.get("command_tool") or "").strip(),
                "command_arg_mode": str(invocation_policy.get("command_arg_mode") or "raw").strip() or "raw",
            }
            if install_specs:
                skill_info["install_recommended"] = install_specs[0].get("id")
            skills.append(skill_info)

        # Workspace skills (highest priority)
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "workspace", len(errors) == 0)

        # Project-local agents skills (next priority)
        if self.project_agents_skills.exists():
            for skill_dir in self.project_agents_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "agents-project", len(errors) == 0)

        # Personal agents skills
        if self.personal_agents_skills.exists():
            for skill_dir in self.personal_agents_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "agents-personal", len(errors) == 0)

        # Managed skills (next priority)
        if self.managed_skills and self.managed_skills.exists():
            for skill_dir in self.managed_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "managed", len(errors) == 0)

        # Built-in skills
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "builtin", len(errors) == 0)

        # Extra skills (lowest priority)
        for extra_dir in self.extra_skill_dirs:
            if not extra_dir.exists():
                continue
            for skill_dir in extra_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "extra", len(errors) == 0)

        # Filter by requirements
        if filter_unavailable:
            result = [s for s in skills if s["eligible"]]
        else:
            result = skills

        self._list_skills_cache[bool(filter_unavailable)] = (
            now,
            roots_snapshot,
            [dict(item) for item in result],
        )
        return result

    def load_skill(self, name: str) -> str | None:
        """
        Load a skill by name.

        Args:
            name: Skill name (directory name).

        Returns:
            Skill content or None if not found.
        """
        name = normalize_skill_reference_name(name)
        if not name:
            return None

        # Check workspace first
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")

        # Check project-local agents skills
        project_agents_skill = self.project_agents_skills / name / "SKILL.md"
        if project_agents_skill.exists():
            return project_agents_skill.read_text(encoding="utf-8")

        # Check personal agents skills
        personal_agents_skill = self.personal_agents_skills / name / "SKILL.md"
        if personal_agents_skill.exists():
            return personal_agents_skill.read_text(encoding="utf-8")

        # Check managed
        if self.managed_skills:
            managed_skill = self.managed_skills / name / "SKILL.md"
            if managed_skill.exists():
                return managed_skill.read_text(encoding="utf-8")

        # Check built-in
        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")

        # Check extra skill dirs
        for extra_dir in self.extra_skill_dirs:
            extra_skill = extra_dir / name / "SKILL.md"
            if extra_skill.exists():
                return extra_skill.read_text(encoding="utf-8")

        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        Load specific skills for inclusion in agent context.

        Args:
            skill_names: List of skill names to load.

        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")

        return "\n\n---\n\n".join(parts) if parts else ""

    def _render_skills_summary(
        self,
        skills: list[dict[str, Any]],
        *,
        root_tag: str = "skills",
    ) -> str:
        if not skills:
            return ""

        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = [f"<{root_tag}>"]
        for s in skills:
            name = escape_xml(s["name"])
            path = s["path"]
            desc = escape_xml(str(s.get("description") or self._get_skill_description(s["name"])))
            available = bool(s.get("eligible"))

            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")

            if not available:
                missing = self._format_skill_unavailability(s)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")

            lines.append("  </skill>")
        lines.append(f"</{root_tag}>")
        return "\n".join(lines)

    def build_skills_summary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).

        This is used for progressive loading - the agent can read the full
        skill content using read_file when needed.

        Returns:
            XML-formatted skills summary.
        """
        roots_snapshot = self._compute_roots_snapshot()
        now = time.time()
        if self._summary_cache:
            cached_at, cached_snapshot, cached_summary = self._summary_cache
            if cached_snapshot == roots_snapshot and (now - cached_at) <= self._list_cache_ttl_seconds:
                return cached_summary

        all_skills = self.list_skills(filter_unavailable=False)
        all_skills = [
            skill for skill in all_skills if not bool(skill.get("disable_model_invocation"))
        ]
        if not all_skills:
            return ""

        summary = self._render_skills_summary(all_skills, root_tag="skills")
        self._summary_cache = (now, roots_snapshot, summary)
        return summary

    def build_skills_summary_for_names(self, skill_names: list[str]) -> str:
        """Build a summary for a selected subset of skills."""
        normalized_names = {
            normalize_skill_reference_name(skill_name)
            for skill_name in (skill_names or [])
            if normalize_skill_reference_name(skill_name)
        }
        if not normalized_names:
            return ""

        selected_skills = [
            skill
            for skill in self.list_skills(filter_unavailable=False)
            if normalize_skill_reference_name(str(skill.get("name") or "")) in normalized_names
            and not bool(skill.get("disable_model_invocation"))
        ]
        if not selected_skills:
            return ""
        return self._render_skills_summary(selected_skills, root_tag="skills")

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        """Get a description of missing requirements."""
        missing = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        missing_os = self._missing_os(skill_meta)
        if missing_os:
            missing.append(f"OS: {', '.join(missing_os)}")
        return ", ".join(missing)

    def _format_skill_unavailability(self, skill_info: dict | None) -> str:
        """Format unavailability reason from list_skills() status payload."""
        if not skill_info:
            return "requirements not met"

        reasons: list[str] = []
        if skill_info.get("disabled"):
            reasons.append("disabled in skills.entries")
        if skill_info.get("blocked_by_allowlist"):
            reasons.append("blocked by allowBundled policy")

        missing = skill_info.get("missing", {})
        if isinstance(missing, dict):
            bins = missing.get("bins", [])
            env = missing.get("env", [])
            os_list = missing.get("os", [])
            if bins:
                reasons.extend(f"CLI: {b}" for b in bins)
            if env:
                reasons.extend(f"ENV: {e}" for e in env)
            if os_list:
                reasons.append(f"OS: {', '.join(os_list)}")

        return ", ".join(reasons) if reasons else "requirements not met"

    def _get_skill_description(self, name: str) -> str:
        """Get the description of a skill from its frontmatter."""
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # Fallback to skill name

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def _parse_kabot_metadata(self, raw: str | dict) -> dict:
        """Parse Kabot and legacy external metadata JSON from frontmatter."""
        if isinstance(raw, dict):
            if isinstance(raw.get("kabot"), dict):
                return raw.get("kabot", {})
            if isinstance(raw.get(_LEGACY_EXTERNAL_METADATA_KEY), dict):
                return raw.get(_LEGACY_EXTERNAL_METADATA_KEY, {})
            return {}
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                return {}
            if isinstance(data.get("kabot"), dict):
                return data.get("kabot", {})
            if isinstance(data.get(_LEGACY_EXTERNAL_METADATA_KEY), dict):
                return data.get(_LEGACY_EXTERNAL_METADATA_KEY, {})
            return {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _platform_aliases(self, platform: str) -> set[str]:
        normalized = (platform or "").strip().lower()
        if normalized == "win32":
            return {"win32", "windows", "win", "nt"}
        if normalized == "darwin":
            return {"darwin", "macos", "mac", "osx"}
        if normalized == "linux":
            return {"linux"}
        return {normalized}

    def _required_os(self, skill_meta: dict) -> list[str]:
        raw_os = skill_meta.get("os")
        if raw_os is None:
            requires = skill_meta.get("requires", {})
            if isinstance(requires, dict):
                raw_os = requires.get("os")
        if raw_os is None:
            return []
        if isinstance(raw_os, str):
            clean = raw_os.strip().lower()
            return [clean] if clean else []
        if isinstance(raw_os, list):
            normalized: list[str] = []
            for value in raw_os:
                clean = str(value).strip().lower()
                if clean:
                    normalized.append(clean)
            return normalized
        return []

    def _missing_os(self, skill_meta: dict) -> list[str]:
        required_os = self._required_os(skill_meta)
        if not required_os:
            return []
        import sys
        aliases = self._platform_aliases(sys.platform)
        if any(target in aliases for target in required_os):
            return []
        return required_os

    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars, OS)."""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        if self._missing_os(skill_meta):
            return False
        return True

    def _get_skill_meta(self, name: str) -> dict:
        """Get kabot metadata for a skill (cached in frontmatter)."""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_kabot_metadata(meta.get("metadata", ""))

    def _resolve_skill_invocation_policy(self, frontmatter: dict | None) -> dict[str, Any]:
        frontmatter = frontmatter if isinstance(frontmatter, dict) else {}
        command_dispatch = str(frontmatter.get("command-dispatch") or "").strip().lower()
        command_tool = str(frontmatter.get("command-tool") or "").strip()
        command_arg_mode = str(frontmatter.get("command-arg-mode") or "raw").strip().lower() or "raw"
        return {
            "user_invocable": _coerce_frontmatter_bool(frontmatter.get("user-invocable"), True),
            "disable_model_invocation": _coerce_frontmatter_bool(
                frontmatter.get("disable-model-invocation"),
                False,
            ),
            "command_dispatch": command_dispatch,
            "command_tool": command_tool,
            "command_arg_mode": command_arg_mode,
        }

    def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        return runtime_get_always_skills(self)

    def _get_skill_metadata_from_file(self, skill_file: Path) -> dict:
        return runtime_get_skill_metadata_from_file(self, skill_file)

    def _get_skill_status(self, name: str) -> dict | None:
        return runtime_get_skill_status(self, name)

    def get_skill_metadata(self, name: str) -> dict | None:
        """
        Get metadata from a skill's frontmatter.

        Args:
            name: Skill name.

        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content:
            return None
        metadata = self._parse_frontmatter_metadata(content)
        return metadata or None

    def _parse_frontmatter_metadata(self, content: str) -> dict:
        return runtime_parse_frontmatter_metadata(content)
