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

_SKILL_CREATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English
    re.compile(
        r"\b(create|build|make|add|design|draft|generate)\b.{0,40}\b"
        r"(skill|skills|plugin|plugins|capability|capabilities|integration|integrations|connector|workflow|automation)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(skill|skills|plugin|plugins|capability|capabilities|integration|integrations|connector|workflow|automation)\b.{0,40}\b"
        r"(new|create|build|make|add|design)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(update|edit|modify|revise|improve|patch|refactor)\b.{0,40}\b"
        r"(skill|skills|plugin|plugins|capability|capabilities|integration|integrations|connector|workflow|automation)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(skill|skills|plugin|plugins|capability|capabilities|integration|integrations|connector|workflow|automation)\b.{0,40}\b"
        r"(update|edit|modify|revise|improve|patch|refactor)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # Indonesian / Malay / mixed colloquial
    re.compile(
        r"\b(buat|bikin|buatkan|tambahkan|tambah|kembangkan|rancang|desain)\b.{0,40}\b"
        r"(skill|skills|plugin|fitur|feature|kemampuan|kapabilitas|integrasi|integration|workflow|otomasi|automation)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(skill|skills|plugin|fitur|feature|kemampuan|kapabilitas|integrasi|integration|workflow|otomasi|automation)\b.{0,40}\b"
        r"(baru|new|buat|bikin|tambahkan|kembangkan)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bbuat\b.{0,16}\b(kemampuan|kapabilitas|integrasi|integration|fitur)\b.{0,16}\b(baru|kabot|api)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(update|edit|ubah|perbarui|modif|modifikasi|revisi|rapikan|improve)\b.{0,40}\b"
        r"(skill|skills|plugin|fitur|feature|kemampuan|kapabilitas|integrasi|integration|workflow|otomasi|automation)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(skill|skills|plugin|fitur|feature|kemampuan|kapabilitas|integrasi|integration|workflow|otomasi|automation)\b.{0,40}\b"
        r"(update|edit|ubah|perbarui|modif|modifikasi|revisi|rapikan|improve)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # Thai
    re.compile(r"(สร้าง|เพิ่ม).{0,20}(สกิล|ปลั๊กอิน|ความสามารถ|การเชื่อมต่อ|อินทิเกรชัน)", re.DOTALL),
    re.compile(r"(สกิล|ปลั๊กอิน|ความสามารถ|การเชื่อมต่อ|อินทิเกรชัน).{0,20}(ใหม่|สร้าง|เพิ่ม)", re.DOTALL),
    re.compile("(\u0E2D\u0E31\u0E1B\u0E40\u0E14\u0E15|\u0E41\u0E01\u0E49\u0E44\u0E02|\u0E1B\u0E23\u0E31\u0E1A\u0E1B\u0E23\u0E38\u0E07).{0,20}(\u0E2A\u0E01\u0E34\u0E25|\u0E1B\u0E25\u0E31\u0E4A\u0E01\u0E2D\u0E34\u0E19|\u0E04\u0E27\u0E32\u0E21\u0E2A\u0E32\u0E21\u0E32\u0E23\u0E16|\u0E01\u0E32\u0E23\u0E40\u0E0A\u0E37\u0E48\u0E2D\u0E21\u0E15\u0E48\u0E2D|\u0E2D\u0E34\u0E19\u0E17\u0E34\u0E40\u0E01\u0E23\u0E0A\u0E31\u0E19)", re.DOTALL),
    re.compile("(\u0E2A\u0E01\u0E34\u0E25|\u0E1B\u0E25\u0E31\u0E4A\u0E01\u0E2D\u0E34\u0E19|\u0E04\u0E27\u0E32\u0E21\u0E2A\u0E32\u0E21\u0E32\u0E23\u0E16|\u0E01\u0E32\u0E23\u0E40\u0E0A\u0E37\u0E48\u0E2D\u0E21\u0E15\u0E48\u0E2D|\u0E2D\u0E34\u0E19\u0E17\u0E34\u0E40\u0E01\u0E23\u0E0A\u0E31\u0E19).{0,20}(\u0E2D\u0E31\u0E1B\u0E40\u0E14\u0E15|\u0E41\u0E01\u0E49\u0E44\u0E02|\u0E1B\u0E23\u0E31\u0E1A\u0E1B\u0E23\u0E38\u0E07)", re.DOTALL),
    # Japanese
    re.compile(r"(新しい|新規).{0,10}(スキル|プラグイン|機能)", re.DOTALL),
    re.compile(r"(スキル|プラグイン|機能).{0,12}(作って|作成|追加|作る)", re.DOTALL),
    re.compile(r"(作って|作成|追加|作る).{0,12}(スキル|プラグイン|機能)", re.DOTALL),
    re.compile("(\u66F4\u65B0|\u4FEE\u6B63|\u6539\u5584|\u7DE8\u96C6).{0,12}(\u30B9\u30AD\u30EB|\u30D7\u30E9\u30B0\u30A4\u30F3|\u6A5F\u80FD)", re.DOTALL),
    re.compile("(\u30B9\u30AD\u30EB|\u30D7\u30E9\u30B0\u30A4\u30F3|\u6A5F\u80FD).{0,12}(\u66F4\u65B0|\u4FEE\u6B63|\u6539\u5584|\u7DE8\u96C6)", re.DOTALL),
    # Chinese
    re.compile(r"(创建|新增|添加|做一个).{0,12}(技能|插件|能力|集成)", re.DOTALL),
    re.compile(r"(技能|插件|能力|集成).{0,12}(创建|新增|添加|做一个|新的)", re.DOTALL),
    re.compile("(\u66F4\u65B0|\u4FEE\u6539|\u7F16\u8F91|\u6539\u8FDB).{0,12}(\u6280\u80FD|\u63D2\u4EF6|\u80FD\u529B|\u96C6\u6210)", re.DOTALL),
    re.compile("(\u6280\u80FD|\u63D2\u4EF6|\u80FD\u529B|\u96C6\u6210).{0,12}(\u66F4\u65B0|\u4FEE\u6539|\u7F16\u8F91|\u6539\u8FDB)", re.DOTALL),
)

_SKILL_INSTALL_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English install/list/update from source/catalog
    re.compile(
        r"\b(install|add|download|fetch|sync|upgrade|update|list|show)\b.{0,50}\b"
        r"(skill|skills|plugin|plugins)\b.{0,50}\b"
        r"(github|repo|repository|url|catalog|catalogue|curated|openai/skills)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(github|repo|repository|url|catalog|catalogue|curated|openai/skills)\b.{0,50}\b"
        r"(skill|skills|plugin|plugins)\b.{0,50}\b"
        r"(install|add|download|fetch|sync|upgrade|update)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(list|show|what)\b.{0,30}\b(installable|available|curated|experimental)\b.{0,30}\b"
        r"(skill|skills|plugin|plugins)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # Indonesian / Malay install/list/update from source/catalog
    re.compile(
        r"\b(install|pasang|tambahkan|unduh|download|sinkron|sync|upgrade|update|tampilkan|lihat|daftar)\b.{0,50}\b"
        r"(skill|skills|plugin|plugins)\b.{0,50}\b"
        r"(github|repo|repository|url|katalog|catalog|catalogue|curated|kurasi|openai/skills)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(github|repo|repository|url|katalog|catalog|catalogue|curated|kurasi|openai/skills)\b.{0,50}\b"
        r"(skill|skills|plugin|plugins)\b.{0,50}\b"
        r"(install|pasang|tambahkan|unduh|download|sinkron|sync|upgrade|update)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(skill|skills|plugin|plugins)\b.{0,40}\b"
        r"(yang tersedia|yang bisa diinstall|yang bisa dipasang|tersedia|installable|available|curated|experimental)\b",
        re.IGNORECASE | re.DOTALL,
    ),
)

_SKILL_CATALOG_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English
    re.compile(
        r"\b(what|which|show|list|available|installable|catalog|catalogue|recommend)\b.{0,40}\b"
        r"(skill|skills)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(skill|skills)\b.{0,40}\b"
        r"(available|installable|list|show|catalog|catalogue|recommend|should i use)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # Indonesian / Malay
    re.compile(
        r"\b(apa|mana|daftar|list|tampilkan|lihat|tersedia|rekomendasi|cocok)\b.{0,32}\b"
        r"(skill|skills)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(skill|skills)\b.{0,32}\b"
        r"(apa|mana|daftar|list|tampilkan|lihat|tersedia|rekomendasi|cocok)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # Thai
    re.compile(r"(มี|รายการ|ลิสต์|แสดง|ดู|แนะนำ).{0,20}(สกิล|ทักษะ)", re.DOTALL),
    re.compile(r"(สกิล|ทักษะ).{0,20}(อะไร|ไหน|มี|รายการ|ลิสต์|แสดง|ดู|แนะนำ)", re.DOTALL),
    # Japanese
    re.compile(r"(どんな|使える|一覧|見せて|教えて|おすすめ).{0,18}(スキル)", re.DOTALL),
    re.compile(r"(スキル).{0,18}(どんな|使える|一覧|ありますか|見せて|教えて|おすすめ)", re.DOTALL),
    # Chinese
    re.compile(r"(有什么|有哪些|列出|显示|看看|推荐).{0,18}(技能)", re.DOTALL),
    re.compile(r"(技能).{0,18}(有什么|有哪些|可以用|列表|列出|显示|推荐)", re.DOTALL),
)

_EXPLICIT_SKILL_USE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(use|run|follow|apply)\b.{0,24}\b(skill|skills)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\b(skill|skills)\b.{0,24}\b(use|run|follow|apply)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\b(pakai|pake|gunakan|jalankan|ikuti)\b.{0,24}\b(skill|skills)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\b(skill|skills)\b.{0,24}\b(pakai|pake|gunakan|jalankan|ikuti)\b", re.IGNORECASE | re.DOTALL),
)

_SKILL_REFERENCE_DECORATION_RE = re.compile(
    r"\s+\[(?:NEEDS|MISSING|DISABLED|BLOCKED)(?::[^\]]*)?\]\s*$",
    re.IGNORECASE,
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
    """Detect natural-language requests to create a new Kabot skill/capability.

    The heuristic stays intentionally broad across languages, but still requires
    a creation/build signal plus an artifact/domain signal so ordinary coding
    requests do not get hijacked.
    """
    content = str(text or "").strip().lower()
    if not content:
        return False
    for pattern in _SKILL_CREATION_PATTERNS:
        if pattern.search(content):
            return True
    return False


def looks_like_skill_install_request(text: str) -> bool:
    """Detect natural-language requests to install/list/update external skills."""
    content = str(text or "").strip().lower()
    if not content:
        return False
    for pattern in _SKILL_INSTALL_PATTERNS:
        if pattern.search(content):
            return True
    return False


def looks_like_skill_catalog_request(text: str) -> bool:
    """Detect requests asking about the skill catalog itself, not using one skill."""
    content = str(text or "").strip().lower()
    if not content:
        return False
    for pattern in _SKILL_CATALOG_PATTERNS:
        if pattern.search(content):
            return True
    return False


def looks_like_explicit_skill_use_request(text: str) -> bool:
    """Detect prompts that explicitly ask to use a named skill."""
    content = str(text or "").strip().lower()
    if not content:
        return False
    if looks_like_skill_catalog_request(content):
        return False
    if looks_like_skill_creation_request(content) or looks_like_skill_install_request(content):
        return False
    for pattern in _EXPLICIT_SKILL_USE_PATTERNS:
        if pattern.search(content):
            return True
    return False


def normalize_skill_reference_name(name: str) -> str:
    """Strip non-canonical status decorations from a skill reference."""
    raw = str(name or "").strip()
    if not raw:
        return ""
    normalized = _SKILL_REFERENCE_DECORATION_RE.sub("", raw).strip()
    return normalized or raw
