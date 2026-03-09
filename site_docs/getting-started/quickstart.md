# Quickstart

## Fastest Reliable Path

```bash
pip install -U kabot
kabot config
kabot gateway
kabot agent -m "Hello Kabot"
```

## A More Realistic First Session

### 1. Start the gateway

```bash
kabot gateway
```

### 2. Open the dashboard

Open:

```text
http://127.0.0.1:<port>/dashboard
```

If gateway auth token is enabled, use the tokenized URL or bearer auth as configured.

### 3. Send a test prompt

```bash
kabot agent -m "What can you help me with?"
```

### 4. Try a practical prompt

```bash
kabot agent -m "Summarize my current Kabot setup goals in 5 bullets."
```

## First Things To Configure After Basic Success

1. Add a fallback model.
2. Open the Gateway menu and set a stable port and auth token.
3. Decide whether you want channels like Telegram or WhatsApp.
4. Decide whether you want hybrid memory enabled.
5. Run a health check.

```bash
kabot doctor --fix
kabot doctor smoke-agent --smoke-timeout 30
```

## Suggested Beginner Milestones

### Milestone 1
- setup wizard saved
- one-shot agent works

### Milestone 2
- dashboard opens
- token/auth access is clear

### Milestone 3
- one channel connected
- one successful end-to-end message

### Milestone 4
- you understand where config, memory, and dashboard fit together
