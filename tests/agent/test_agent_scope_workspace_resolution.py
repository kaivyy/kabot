from pathlib import Path

from kabot.agent.agent_scope import resolve_agent_id_for_workspace
from kabot.config.schema import AgentConfig, Config


def test_resolve_agent_id_for_workspace_prefers_most_specific_match(tmp_path: Path):
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "default-workspace")
    cfg.agents.agents = [
        AgentConfig(id="repo", workspace=str(tmp_path / "projects" / "acme")),
        AgentConfig(id="api", workspace=str(tmp_path / "projects" / "acme" / "services" / "api")),
    ]

    detected = resolve_agent_id_for_workspace(
        cfg,
        tmp_path / "projects" / "acme" / "services" / "api" / "src",
    )

    assert detected == "api"


def test_resolve_agent_id_for_workspace_falls_back_to_default_agent(tmp_path: Path):
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "default-workspace")
    cfg.agents.agents = [
        AgentConfig(id="main", default=True, workspace=str(tmp_path / "default-workspace")),
        AgentConfig(id="repo", workspace=str(tmp_path / "projects" / "acme")),
    ]

    detected = resolve_agent_id_for_workspace(cfg, tmp_path / "unrelated")

    assert detected == "main"
