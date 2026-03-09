# Beginner Track

This section is for people who want the shortest reliable path from zero to a working Kabot instance.

## The 5-Step Path

1. Install Kabot.
2. Run `kabot config`.
3. Choose at least one model provider.
4. Start `kabot gateway`.
5. Test with `kabot agent -m "Hello Kabot"`.

## Who This Track Is For

Use this track if you are:
- new to local AI tooling
- not sure which config options matter yet
- trying Kabot on Windows, macOS, Linux, or Termux
- more interested in getting it running than reading architecture first

## Beginner Success Criteria

You are done with the beginner track when:
- the setup wizard saves without errors
- `kabot gateway` starts cleanly
- the dashboard opens
- a one-shot CLI message works
- you understand where to edit config later

## Reading Order

1. [Install](install.md)
2. [First Run](first-run.md)
3. [Quickstart](quickstart.md)
4. [Dashboard](dashboard.md)

## If You Want The Shortest Version

<div class="kabot-terminal">
<strong>Install</strong>

```bash
pip install -U kabot
kabot config
kabot gateway
kabot agent -m "Hello Kabot"
```
</div>
