---
name: config-manager
description: Inspect and safely update Kabot configuration, model/memory/provider settings, channel account policies, allowlists, and related status or log evidence when debugging why a setting or runtime behavior is wrong.
metadata: { "kabot": { "adapt": { "groundedDiagnostics": true } } }
---

# Config Manager

Use this skill when the user asks whether a Kabot setting is enabled, why a config value is not taking effect, why a model/provider/channel setup is failing, or asks you to safely edit Kabot config after reviewing the current state.

## Use this skill for

- `~/.kabot/config.json`, `config.json.bak`, or `mode_config.json`
- model/provider/memory/backend settings
- channel settings such as WhatsApp, Telegram, Discord, accounts, allowlists, pairing, or login-related config
- conflicting top-level vs per-account config
- invalid JSON, missing keys, missing env-backed settings, or wrong defaults
- runtime issues where the next grounded step is to inspect config, status output, or logs before changing anything

## Grounding rules

- Read the real config first. Do not guess from defaults.
- When the issue is runtime behavior, inspect the relevant status output and logs before proposing a fix.
- Separate explicit config from code fallback/default behavior. Say which is which.
- Prefer the smallest safe config change that resolves the issue.
- Ask for approval before any state-changing edit, restart, reload, relink, or destructive cleanup.

## Files and evidence to inspect

- `~/.kabot/config.json`
- `~/.kabot/config.json.bak`
- `~/.kabot/mode_config.json`
- `~/.kabot/logs/`
- relevant workspace docs/bootstrap files if the user references them
- relevant runtime status output if available

## Workflow

1. Ground the request in real evidence

- Identify the exact setting, subsystem, or symptom the user cares about.
- Read only the relevant config sections first.
- If the user asks "is X configured?", answer from the file, not from assumption.
- If the issue is a runtime error, compare config with the latest relevant log/status evidence.

2. Diagnose before editing

- Quote the current relevant values briefly.
- Call out missing keys, conflicting overrides, duplicated account blocks, malformed JSON, or env/config gaps.
- If the value is not explicitly set, say whether Kabot is falling back to a code default and where that default comes from.

3. Propose the minimal fix

- Show the exact field(s) to add, remove, or change.
- Explain why the change is needed.
- Mention any risk such as relogin, restart, account routing change, or lost fallback behavior.

4. Execute only after approval

- Edit only the approved scope.
- Preserve backups when possible.
- Validate JSON after editing, for example with:

```bash
python -m json.tool ~/.kabot/config.json
```

or:

```bash
jq '.' ~/.kabot/config.json
```

5. Verify after change

- Re-read the changed config section.
- If the change requires reload/restart, do that only with approval.
- Re-check status/log evidence and say whether the fix is verified or still pending.

## Channel/account troubleshooting reminders

- Compare top-level `channels.<name>` settings with per-account overrides under `accounts`.
- Watch for duplicated allowlists, mismatched policies, or multiple accounts creating ambiguous routing.
- For pairing/login/session issues, distinguish config problems from auth/session problems. Do not blame config if the logs show the session is simply logged out.

## Model and memory reminders

- For "is model X configured?" or "is embedding model Y set?", inspect config first.
- If the setting is absent, say whether Kabot will fall back to a runtime default and cite the relevant code/config source if needed.
- Do not claim a local model is active unless config or status/log evidence supports it.
