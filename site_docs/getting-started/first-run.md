# First Run

## Step 1: Open The Setup Wizard

```bash
kabot config
```

This is the main setup surface for most users.

## Step 2: Configure A Model Provider

Inside the wizard, start with `Model / Auth`.

Recommended beginner flow:
- login to one provider first
- let Kabot auto-build a primary model path
- only add manual override models after the basics work

Good first providers for many users:
- OpenAI
- Anthropic
- Gemini
- Groq
- OpenRouter
- Ollama (Local Auto-Discovery)

## Step 3: Save Configuration

Once the wizard saves:
- Kabot writes config into your local runtime area
- provider credentials are stored locally
- later menus like Channels, Skills, and Gateway can reuse that config

## Step 4: Start The Gateway

```bash
kabot gateway
```

Expected result:
- Kabot starts listening on the configured gateway port
- dashboard routes become available
- channel/webhook ingress becomes available if configured

## Step 5: Test CLI Chat

```bash
kabot agent -m "Hello Kabot"
```

This verifies:
- CLI entrypoint works
- your model config is usable
- Kabot can build runtime context and answer

## If Something Fails

Go to:
- [Configuration guide](../guide/configuration.md)
- [Troubleshooting](../guide/troubleshooting.md)

And run:

```bash
kabot doctor --fix
```

## Important Mental Model

Kabot has a few core surfaces:

- `kabot config` for setup and operator configuration
- `kabot gateway` for the web/dashboard and ingress runtime
- `kabot agent` for direct chat and one-shot prompts
- `kabot doctor` for diagnostics and smoke checks
