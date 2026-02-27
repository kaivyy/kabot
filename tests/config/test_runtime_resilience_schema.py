from kabot.config.schema import Config


def test_runtime_resilience_and_performance_defaults_present():
    cfg = Config()

    assert cfg.runtime.resilience.enabled is True
    assert cfg.runtime.resilience.max_model_attempts_per_turn == 4
    assert cfg.runtime.resilience.idempotency_ttl_seconds == 600

    assert cfg.runtime.performance.fast_first_response is True
    assert cfg.runtime.performance.defer_memory_warmup is True
    assert cfg.runtime.performance.max_first_response_ms_soft == 4000
    assert cfg.runtime.autopilot.enabled is True
    assert cfg.runtime.autopilot.max_actions_per_beat == 1


def test_skills_payload_is_normalized_into_typed_schema():
    cfg = Config.model_validate(
        {
            "skills": {
                "notion": {"env": {"NOTION_API_KEY": "abc"}},
                "install": {"mode": "auto", "nodeManager": "pnpm"},
            }
        }
    )

    assert "notion" in cfg.skills.entries
    assert cfg.skills.entries["notion"].env["NOTION_API_KEY"] == "abc"
    assert cfg.skills.install.mode == "auto"
    assert cfg.skills.install.node_manager == "pnpm"
