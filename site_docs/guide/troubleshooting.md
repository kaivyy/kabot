# Troubleshooting

This page is for the most common failures when getting Kabot running or stable.

## Start Here

```bash
kabot doctor --fix
kabot doctor routing
kabot doctor smoke-agent --smoke-timeout 30
```

## Problem: CLI Works Poorly Or Feels Inconsistent

Check:
- model auth is valid
- one-shot prompts are using the expected config
- your shell is not damaging Unicode input

Use one short test:

```bash
kabot agent -m "hari apa sekarang? jawab singkat"
```

## Problem: Gateway Starts But Dashboard Feels Wrong

Check:
- correct port
- correct auth token or query token
- active dashboard scope (`operator.read` vs `operator.write`)
- any reverse proxy or bind mode mismatch

## Problem: Channels Are Silent

Check:
- token/credential validity
- `allowFrom`
- channel binding to the right agent
- bridge health for bridge-based adapters

## Problem: Memory Is Heavy Or Slow

Try:
- a lighter memory path
- lighter model choices
- one-shot smoke checks before interactive deep sessions
- Termux-specific low-RAM adjustments

## Problem: Non-ASCII Prompts In Windows Shells

Kabot now has runtime hardening for mojibake-style shell input damage, but modern UTF-8 capable terminals are still the safest path.

## Termux And Low-RAM Notes

On constrained devices:
- prefer lighter models
- avoid unnecessary heavy memory features at first
- test with one channel and one model before expanding

## When To Escalate

Collect:
- the exact command
- the exact error
- whether it happens only in CLI, only in dashboard, or both
- whether it is tied to one model/provider or all of them
