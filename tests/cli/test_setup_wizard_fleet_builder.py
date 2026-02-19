from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard


def test_apply_fleet_template_creates_instances_and_agents(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    wizard._apply_fleet_template(
        template_id="content_pipeline",
        channel_type="telegram",
        base_id="team",
        bot_tokens=["tok1", "tok2", "tok3"],
    )

    assert len(wizard.config.channels.instances) == 3
    assert len(wizard.config.agents.agents) >= 3
    assert all(inst.agent_binding for inst in wizard.config.channels.instances)
