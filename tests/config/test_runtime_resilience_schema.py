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
    assert cfg.runtime.observability.enabled is True
    assert cfg.runtime.observability.emit_structured_events is True
    assert cfg.runtime.observability.sample_rate == 1.0
    assert cfg.runtime.observability.redact_secrets is True
    assert cfg.runtime.quotas.enabled is False
    assert cfg.runtime.quotas.max_cost_per_day_usd == 0.0
    assert cfg.runtime.quotas.max_tokens_per_hour == 0
    assert cfg.runtime.quotas.enforcement_mode == "warn"
    assert cfg.runtime.queue.enabled is True
    assert cfg.runtime.queue.mode == "debounce"
    assert cfg.runtime.queue.debounce_window_ms == 1200
    assert cfg.runtime.queue.max_pending_per_session == 4
    assert cfg.runtime.queue.drop_policy == "drop_oldest"
    assert cfg.runtime.queue.summarize_dropped is True
    assert cfg.agents.defaults.heartbeat.startup_delay_seconds == 120
    assert cfg.security.trust_mode.enabled is False
    assert cfg.security.trust_mode.verify_skill_manifest is False
    assert cfg.security.trust_mode.allowed_signers == []
    assert cfg.skills.onboarding.auto_prompt_env is True
    assert cfg.skills.onboarding.auto_enable_after_install is True
    assert cfg.skills.onboarding.soul_injection_mode == "prompt"


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
