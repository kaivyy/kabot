"""Skills loader for agent capabilities."""

import logging
import re
from pathlib import Path

# Default builtin skills directory (relative to this file)
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"

logger = logging.getLogger(__name__)

# Workflow chains: when skill X matches, also suggest related skills
WORKFLOW_CHAINS: dict[str, list[str]] = {
    "brainstorming": ["writing-plans", "executing-plans"],
    "writing-plans": ["executing-plans"],
    "systematic-debugging": ["test-driven-development"],
    "executing-plans": ["finishing-a-development-branch"],
    "requesting-code-review": ["finishing-a-development-branch"],
}

# Stop words to ignore when matching (multilingual)
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "or", "and", "not", "no", "it", "its", "this", "that",
    "use", "using", "when", "you", "your", "via", "can", "do",
    "tool", "tools", "skill", "skills",
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "untuk",
    "pakai", "pake", "pakaiin",
})

_SKILL_DOMAIN_KEYWORDS = frozenset({
    "skill", "skills", "plugin", "plugins", "capability", "capabilities",
    "integration", "integrations", "connector", "workflow", "automation",
    "fitur", "feature", "kemampuan", "kapabilitas", "integrasi", "otomasi",
})

_SKILL_CREATE_UPDATE_KEYWORDS = frozenset({
    "create", "build", "make", "add", "design", "draft", "generate", "new",
    "update", "edit", "modify", "revise", "improve", "patch", "refactor",
    "buat", "bikin", "buatkan", "tambahkan", "tambah", "kembangkan", "rancang",
    "desain", "baru", "ubah", "perbarui", "modif", "modifikasi", "revisi",
    "rapikan",
})

_SKILL_INSTALL_KEYWORDS = frozenset({
    "install", "add", "download", "fetch", "sync", "upgrade", "update",
    "pasang", "tambahkan", "unduh", "sinkron",
})

_SKILL_DISCOVERY_KEYWORDS = frozenset({
    "list", "show", "what", "which", "available", "installable", "catalog",
    "catalogue", "curated", "experimental", "recommend", "rekomendasi",
    "daftar", "tampilkan", "lihat", "tersedia", "cocok", "apa", "mana",
})

_SKILL_SOURCE_KEYWORDS = frozenset({
    "github", "repo", "repository", "url", "catalog", "catalogue",
    "curated", "kurasi", "openai/skills",
})

_SKILL_USE_KEYWORDS = frozenset({
    "use", "run", "follow", "apply", "gunakan", "pakai", "pake",
    "jalankan", "ikuti",
})

_COMPACT_SKILL_DOMAIN_FRAGMENTS = (
    "สกิล", "ปลั๊กอิน", "ความสามารถ", "การเชื่อมต่อ", "อินทิเกรชัน", "ทักษะ",
    "スキル", "プラグイン", "機能",
    "技能", "插件", "能力", "集成",
)

_COMPACT_CREATE_UPDATE_FRAGMENTS = (
    "สร้าง", "เพิ่ม", "ใหม่", "อัปเดต", "แก้ไข", "ปรับปรุง",
    "新しい", "新規", "作って", "作成", "追加", "作る", "更新", "修正", "改善", "編集",
    "创建", "新增", "添加", "做一个", "更新", "修改", "编辑", "改进",
)

_COMPACT_INSTALL_FRAGMENTS = (
    "ติดตั้ง", "インストール", "安装",
)

_COMPACT_CATALOG_FRAGMENTS = (
    "มี", "รายการ", "ลิสต์", "แสดง", "ดู", "แนะนำ", "อะไร",
    "どんな", "使える", "一覧", "見せて", "教えて", "おすすめ", "ありますか",
    "有什么", "有哪些", "列出", "显示", "看看", "推荐", "可以用", "列表",
)

_COMPACT_USE_FRAGMENTS = (
    "ใช้", "使って", "使う", "用这个",
)

_DIRECT_GITHUB_SKILL_URL_RE = re.compile(
    r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:tree|blob)/[^/\s]+/[^\s#]*(?:/skills?/[^ \t\r\n#]+|/SKILL\.md)\b",
    re.IGNORECASE,
)
_DIRECT_GITHUB_SKILL_PATH_RE = re.compile(
    r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:skills?/[^ \t\r\n#]+|[^ \t\r\n#]*/SKILL\.md)\b",
    re.IGNORECASE,
)
_SKILL_INSTALL_ACTION_RE = re.compile(
    r"\b("
    r"install|pasang|tambahkan|unduh|download|sinkron|sync|upgrade|update|"
    r"use|gunakan|pakai|pake|follow|ikuti"
    r")\b",
    re.IGNORECASE,
)

_SKILL_NAMEISH_RE = re.compile(r"\b[a-z0-9]+(?:[-_][a-z0-9]+){1,}\b", re.IGNORECASE)

_SKILL_REFERENCE_DECORATION_RE = re.compile(
    r"\s+\[(?:NEEDS|MISSING|DISABLED|BLOCKED)(?::[^\]]*)?\]\s*$",
    re.IGNORECASE,
)


def _contains_any_fragment(text: str, fragments: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(fragment.lower() in lowered for fragment in fragments)


def _intent_tokens(text: str) -> set[str]:
    normalized = re.sub(r"[^\w/+-]+", " ", str(text or "").lower(), flags=re.UNICODE)
    return {token for token in normalized.split() if token}


def _has_keyword_signal(text: str, keywords: frozenset[str]) -> bool:
    return bool((_extract_keywords(text) | _intent_tokens(text)) & keywords)


def _has_skill_domain_signal(text: str) -> bool:
    return _has_keyword_signal(text, _SKILL_DOMAIN_KEYWORDS) or _contains_any_fragment(
        text, _COMPACT_SKILL_DOMAIN_FRAGMENTS
    )


def _has_skill_create_or_update_signal(text: str) -> bool:
    return _has_keyword_signal(text, _SKILL_CREATE_UPDATE_KEYWORDS) or _contains_any_fragment(
        text, _COMPACT_CREATE_UPDATE_FRAGMENTS
    )


def _has_skill_install_signal(text: str) -> bool:
    return _has_keyword_signal(text, _SKILL_INSTALL_KEYWORDS) or _contains_any_fragment(
        text, _COMPACT_INSTALL_FRAGMENTS
    )


def _has_skill_discovery_signal(text: str) -> bool:
    return _has_keyword_signal(text, _SKILL_DISCOVERY_KEYWORDS) or _contains_any_fragment(
        text, _COMPACT_CATALOG_FRAGMENTS
    )


def _has_skill_source_signal(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    return any(keyword in lowered for keyword in _SKILL_SOURCE_KEYWORDS)


def _has_explicit_skill_use_signal(text: str) -> bool:
    return _has_keyword_signal(text, _SKILL_USE_KEYWORDS) or _contains_any_fragment(
        text, _COMPACT_USE_FRAGMENTS
    )


def _naive_stem(word: str) -> str:
    """Very basic suffix stripping for keyword matching.

    Not a real stemmer — just enough to match 'debugging'→'debug',
    'plans'→'plan', 'writing'→'write', etc.
    """
    if len(word) <= 4:
        return word
    for suffix in ("ation", "tion", "ment", "ness", "ity", "ing", "ies", "ed", "ly", "es", "er", "al", "ful"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[:-len(suffix)]
            # Handle doubled consonant: debugging→debugg→debug, running→runn→run
            if len(stem) >= 4 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                stem = stem[:-1]
            # Handle silent 'e' restoration after -ing: writing→writ→write, creating→creat→create
            if suffix == "ing" and len(stem) >= 3 and stem[-1] in "tdkcvz":
                stem += "e"
            return stem
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]
    return word


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, filtering stop words + stemming."""
    words = re.findall(r'[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u0E00-\u0E7F\u3000-\u9FFF\uAC00-\uD7AF]{2,}', text.lower())
    stemmed = {_naive_stem(w) for w in words if w not in _STOP_WORDS}
    # Also keep original words (so "debug" matches "debug" directly)
    originals = {w for w in words if w not in _STOP_WORDS}
    return stemmed | originals


def _intent_alias_bonus(skill_name: str, message_lower: str) -> float:
    """Provide intent-level boost for well-known workflow skills."""
    normalized_skill = (skill_name or "").strip().lower()
    if not normalized_skill:
        return 0.0

    if normalized_skill == "skill-installer":
        if looks_like_skill_install_request(message_lower):
            return 6.5
        patterns = (
            r"\b(skill[\s_-]?installer|install(?:able)? skills?|curated skills?)\b",
        )
        for pattern in patterns:
            if re.search(pattern, message_lower):
                return 6.5

    if normalized_skill in {"skill-creator", "writing-skills"}:
        if looks_like_skill_creation_request(message_lower):
            return 6.0
        patterns = (
            r"\b(skill[\s_-]?creator|skills? creator|skill[\s_-]?builder)\b",
        )
        for pattern in patterns:
            if re.search(pattern, message_lower):
                return 6.0
    return 0.0


def looks_like_skill_creation_request(text: str) -> bool:
    """Detect requests to create or update a skill workflow.

    This intentionally stays structural: it looks for a skill-domain signal plus
    a create/update action, instead of relying on long phrase buckets.
    """
    content = str(text or "").strip()
    if not content:
        return False
    return _has_skill_domain_signal(content) and _has_skill_create_or_update_signal(content)


def looks_like_skill_install_request(text: str) -> bool:
    """Detect natural-language requests to install/list/update external skills."""
    content = str(text or "").strip()
    if not content:
        return False
    has_install = _has_skill_install_signal(content)
    has_domain = _has_skill_domain_signal(content)
    has_source = _has_skill_source_signal(content)
    has_discovery = _has_skill_discovery_signal(content)

    if _DIRECT_GITHUB_SKILL_URL_RE.search(content) and (_SKILL_INSTALL_ACTION_RE.search(content) or has_discovery):
        return True
    if _DIRECT_GITHUB_SKILL_PATH_RE.search(content) and (_SKILL_INSTALL_ACTION_RE.search(content) or has_discovery):
        return True
    if has_install and (has_domain or has_source):
        return True
    if has_domain and has_source and has_discovery:
        return True
    return False


def looks_like_skill_catalog_request(text: str) -> bool:
    """Detect requests asking about the skill catalog itself, not using one skill."""
    content = str(text or "").strip()
    if not content:
        return False
    return _has_skill_domain_signal(content) and _has_skill_discovery_signal(content)


def looks_like_explicit_skill_use_request(text: str) -> bool:
    """Detect prompts that explicitly ask to use a named skill."""
    content = str(text or "").strip()
    if not content:
        return False
    if looks_like_skill_catalog_request(content):
        return False
    if looks_like_skill_creation_request(content) or looks_like_skill_install_request(content):
        return False
    if not _has_explicit_skill_use_signal(content):
        return False
    return _has_skill_domain_signal(content) or bool(
        _DIRECT_GITHUB_SKILL_URL_RE.search(content)
        or _DIRECT_GITHUB_SKILL_PATH_RE.search(content)
        or _SKILL_NAMEISH_RE.search(content)
    )


def normalize_skill_reference_name(name: str) -> str:
    """Strip non-canonical status decorations from a skill reference."""
    raw = str(name or "").strip()
    if not raw:
        return ""
    normalized = _SKILL_REFERENCE_DECORATION_RE.sub("", raw).strip()
    return normalized or raw
