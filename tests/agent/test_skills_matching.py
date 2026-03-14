import os
from pathlib import Path

from kabot.agent.skills import SkillsLoader, looks_like_skill_catalog_request

_LEGACY_EXTERNAL_METADATA_KEY = "".join(
    chr(code) for code in (111, 112, 101, 110, 99, 108, 97, 119)
)


def _write_skill(skill_root: Path, skill_name: str, body: str) -> None:
    skill_dir = skill_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: test skill\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_match_skills_does_not_auto_load_irrelevant_tool_skills(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills("jadi tools mu yang bermasalah?", profile="GENERAL")
    assert "mcporter" not in matches
    assert "sherpa-onnx-tts" not in matches


def test_match_skills_supports_thai_keywords(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "cleanup-th", "ล้างแคช ดิสก์ ลบไฟล์ชั่วคราว")

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills("ช่วยล้างแคชดิสก์ให้หน่อย", profile="GENERAL")

    assert any(m.startswith("cleanup-th") for m in matches)


def test_match_skills_prioritizes_explicit_skill_name(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "clawra-selfie", "generate selfie image")
    _write_skill(
        workspace / "skills",
        "generic-image",
        "generate selfie image portrait photo camera selfie image generator edit create",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills(
        "please use clawra-selfie skill to generate selfie image portrait photo now",
        profile="GENERAL",
    )

    assert matches
    assert any(m.startswith("generic-image") for m in matches)
    assert matches[0].startswith("clawra-selfie")


def test_match_skills_preserves_explicit_digit_heavy_full_name_match(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "1password", "vault credential manager")
    _write_skill(
        workspace / "skills",
        "password-helper",
        "password vault credential manager login secure account",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills(
        "please use 1password skill for this password vault login task",
        profile="GENERAL",
    )

    assert matches
    assert any(m.startswith("password-helper") for m in matches)
    assert matches[0].startswith("1password")


def test_match_skills_explicit_skill_turn_skips_full_index(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "weather", "forecast temperature rain wind humidity")

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    monkeypatch.setattr(
        loader,
        "_build_skill_index",
        lambda: (_ for _ in ()).throw(AssertionError("_build_skill_index should not be called")),
    )
    monkeypatch.setattr(
        loader,
        "list_skills",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("list_skills should not be called")),
    )

    matches = loader.match_skills("Please use the weather skill for this request.", profile="GENERAL")

    assert matches
    assert matches[0].startswith("weather")


def test_match_skills_skips_disable_model_invocation_skill_for_natural_language_request(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    hidden_skill_dir = workspace / "skills" / "internal-ledger"
    hidden_skill_dir.mkdir(parents=True, exist_ok=True)
    (hidden_skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: internal-ledger\n"
            "description: Internal ledger control skill\n"
            "disable-model-invocation: true\n"
            "---\n\n"
            "# Skill\n"
        ),
        encoding="utf-8",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills(
        "please use the internal-ledger skill for this request",
        profile="GENERAL",
    )

    assert not matches


def test_match_skills_non_explicit_turn_still_uses_full_index(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "weather", "forecast temperature rain wind humidity")

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    calls = {"count": 0}
    original = loader._build_skill_index

    def _build():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(loader, "_build_skill_index", _build)

    matches = loader.match_skills("forecast temperature rain today", profile="GENERAL")

    assert calls["count"] == 1
    assert matches
    assert matches[0].startswith("weather")


def test_match_skills_understands_create_new_skill_intent_for_skill_creator(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace / "skills",
        "skill-creator",
        "guide for creating a new skill workflow and SKILL.md structure",
    )
    _write_skill(
        workspace / "skills",
        "generic-dev",
        "build app script code automation helper development",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills("saya mau buat skill baru untuk telegram", profile="GENERAL")

    assert matches
    assert matches[0].startswith("skill-creator")


def test_match_skills_understands_capability_creation_intent_for_skill_creator(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace / "skills",
        "skill-creator",
        "guide for creating a new skill workflow and SKILL.md structure",
    )
    _write_skill(
        workspace / "skills",
        "generic-dev",
        "build app script code automation helper development",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    assert loader.match_skills("buat kemampuan baru buat kabot", profile="GENERAL")[0].startswith("skill-creator")
    assert loader.match_skills(
        "create a capability for posting to threads",
        profile="GENERAL",
    )[0].startswith("skill-creator")


def test_match_skills_understands_skill_update_intent_for_skill_creator(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace / "skills",
        "skill-creator",
        "guide for creating or updating a skill workflow and SKILL.md structure",
    )
    _write_skill(
        workspace / "skills",
        "generic-dev",
        "build app script code automation helper development",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    assert loader.match_skills("tolong update skill threads yang sudah ada", profile="GENERAL")[0].startswith("skill-creator")
    assert loader.match_skills(
        "please edit the existing threads skill",
        profile="GENERAL",
    )[0].startswith("skill-creator")


def test_match_skills_understands_external_skill_install_intent_for_skill_installer(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace / "skills",
        "skill-installer",
        "install curated skills from GitHub repo URL catalog openai/skills",
    )
    _write_skill(
        workspace / "skills",
        "generic-dev",
        "build app script code automation helper development",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    assert loader.match_skills(
        "tolong install skill dari github repo owner/repo",
        profile="GENERAL",
    )[0].startswith("skill-installer")
    assert loader.match_skills(
        "show me installable curated skills from openai/skills",
        profile="GENERAL",
    )[0].startswith("skill-installer")


def test_match_skills_understands_multilingual_skill_creation_intent(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace / "skills",
        "skill-creator",
        "guide for creating a new skill workflow and SKILL.md structure",
    )
    _write_skill(
        workspace / "skills",
        "generic-dev",
        "build app script code automation helper development",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    for phrase in (
        "ช่วยสร้างสกิลใหม่ไว้โพสต์ Threads",
        "Threads投稿用の新しいスキルを作って",
        "帮我创建一个新技能，用于发 Threads",
    ):
        matches = loader.match_skills(phrase, profile="GENERAL")
        assert matches
        assert matches[0].startswith("skill-creator")


def test_match_skills_does_not_confuse_meta_threads_with_discord(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace / "skills",
        "skill-creator",
        "guide for creating a new skill workflow and SKILL.md structure",
    )
    _write_skill(
        workspace / "skills",
        "discord",
        "discord thread server guild channel message moderation reply bot",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    create_matches = loader.match_skills(
        "bisakah bikin skills untuk koneksi ke meta threads",
        profile="GENERAL",
    )
    general_matches = loader.match_skills(
        "konek ke meta threads bisa?",
        profile="GENERAL",
    )

    assert create_matches
    assert create_matches[0].startswith("skill-creator")
    assert not any(match.startswith("discord") for match in create_matches)
    assert not any(match.startswith("discord") for match in general_matches)


def test_match_skills_understands_multilingual_skill_update_intent(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace / "skills",
        "skill-creator",
        "guide for creating or updating a skill workflow and SKILL.md structure",
    )
    _write_skill(
        workspace / "skills",
        "generic-dev",
        "build app script code automation helper development",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    for phrase in (
        "天気スキルを更新してUV indexも見られるようにして",
        "ช่วยอัปเดตสกิลอากาศให้เช็กค่า UV index ได้ด้วย",
        "帮我更新天气技能，让它也能检查 UV index",
    ):
        matches = loader.match_skills(phrase, profile="GENERAL")
        assert matches
        assert matches[0].startswith("skill-creator")


def test_looks_like_skill_catalog_request_supports_multilingual_inventory_questions():
    assert looks_like_skill_catalog_request("what skills are available in this workspace?")
    assert looks_like_skill_catalog_request("skill apa yang tersedia di workspace ini?")
    assert looks_like_skill_catalog_request("有哪些技能可以用？")
    assert looks_like_skill_catalog_request("使えるスキル一覧を見せて")
    assert looks_like_skill_catalog_request("มีสกิลอะไรให้ใช้บ้าง")

    assert looks_like_skill_catalog_request("Please use the weather skill for this request.") is False
    assert looks_like_skill_catalog_request("tolong pakai skill 1password untuk request ini ya.") is False


def test_list_skills_uses_snapshot_cache(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "cached-skill", "cached summary check")

    calls = {"count": 0}

    def _validate_skill(_skill_dir: Path):
        calls["count"] += 1
        return []

    monkeypatch.setattr("kabot.agent.skills.validate_skill", _validate_skill)

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    first = loader.list_skills(filter_unavailable=True)
    second = loader.list_skills(filter_unavailable=True)

    assert first
    assert second
    assert calls["count"] == 1


def test_list_skills_invalidates_cache_when_runtime_env_changes(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    skill_dir = workspace / "skills" / "binance-pro"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: binance-pro",
                "description: crypto execution skill",
                f'metadata: {{"{_LEGACY_EXTERNAL_METADATA_KEY}":{{"requires":{{"bins":["jq"]}}}}}}',
                "---",
                "",
                "Use this for crypto account workflows.",
            ]
        ),
        encoding="utf-8",
    )

    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PATH", str(empty_bin))

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    first = loader.list_skills(filter_unavailable=False)
    assert first and first[0]["eligible"] is False

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "jq.cmd").write_text("@echo off\necho {}\n", encoding="ascii")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{empty_bin}")

    second = loader.list_skills(filter_unavailable=False)
    assert second and second[0]["eligible"] is True


def test_legacy_external_metadata_is_accepted_for_always_skill(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    skill_dir = workspace / "skills" / "binance-pro"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: binance-pro",
                "description: crypto execution skill",
                f'metadata: {{"{_LEGACY_EXTERNAL_METADATA_KEY}":{{"always":true}}}}',
                "---",
                "",
                "Use this for crypto account workflows.",
            ]
        ),
        encoding="utf-8",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    assert "binance-pro" in loader.get_always_skills()


def test_external_finance_skill_is_still_preferred_even_when_requirements_missing(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    skill_dir = workspace / "skills" / "binance-pro"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: binance-pro",
                "description: crypto trading and binance market operations",
                f'metadata: {{"{_LEGACY_EXTERNAL_METADATA_KEY}":{{"requires":{{"bins":["jq"]}}}}}}',
                "---",
                "",
                "Use for crypto trading tasks.",
            ]
        ),
        encoding="utf-8",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    assert loader.should_prefer_external_finance_skill("cek harga btc sekarang", profile="GENERAL") is True


def test_crypto_only_finance_skill_does_not_match_stock_query(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    skill_dir = workspace / "skills" / "binance-pro"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: binance-pro",
                "description: crypto trading and binance market operations",
                "---",
                "",
                "Use for crypto account workflows.",
            ]
        ),
        encoding="utf-8",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    assert "binance-pro" not in loader.match_skills(
        "cek harga saham bca bri mandiri adaro sekarang",
        profile="GENERAL",
    )
    assert (
        loader.should_prefer_external_finance_skill(
            "cek harga saham bca bri mandiri adaro sekarang",
            profile="GENERAL",
        )
        is False
    )


def test_generic_finance_skill_can_match_stock_query(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    skill_dir = workspace / "skills" / "market-intel"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: market-intel",
                'description: analyze stocks, crypto, market quotes, watchlists, and tickers"',
                "---",
                "",
                "Use for broad market research tasks.",
            ]
        ),
        encoding="utf-8",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)

    assert "market-intel" in loader.match_skills(
        "cek harga saham bca bri mandiri adaro sekarang",
        profile="GENERAL",
    )
    assert (
        loader.should_prefer_external_finance_skill(
            "cek harga saham bca bri mandiri adaro sekarang",
            profile="GENERAL",
        )
        is True
    )
