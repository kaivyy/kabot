from pathlib import Path

from kabot.agent.skills import SkillsLoader


def test_match_skills_does_not_auto_load_irrelevant_tool_skills():
    loader = SkillsLoader(Path("."))
    matches = loader.match_skills("jadi tools mu yang bermasalah?", profile="GENERAL")
    assert "mcporter" not in matches
    assert "sherpa-onnx-tts" not in matches
