from pathlib import Path

MOJIBAKE_MARKERS = ("â”", "âœ", "â—", "ðŸ", "Ã—")


def test_wizard_ui_files_do_not_contain_mojibake_markers():
    files = [
        Path("kabot/cli/setup_wizard.py"),
        Path("kabot/cli/wizard/ui.py"),
        Path("kabot/cli/wizard/sections/core.py"),
        Path("kabot/cli/wizard/sections/model_auth.py"),
        Path("kabot/cli/wizard/sections/channels.py"),
        Path("kabot/cli/wizard/sections/tools_gateway_skills.py"),
        Path("kabot/cli/wizard/sections/operations.py"),
        Path("kabot/auth/manager.py"),
    ]

    offenders: list[str] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            offenders.append(str(file_path))

    assert offenders == []
