# Channels Guide

Channels let people talk to Kabot from real messaging surfaces instead of only the CLI.

## What Channels Are For

Channels are how Kabot becomes operational in the real world.

Instead of asking every user to open a local shell, you can expose Kabot through:
- direct messaging bots
- team chat platforms
- bridge-backed chat services
- channel-specific agents

Good use cases:
- a personal Telegram bot
- a Discord helper for your server
- an internal Slack assistant
- a WhatsApp-based support or family workflow

## Common Channel Types

Kabot supports a broad set of channels and adapters, including:
- Telegram
- Discord
- Slack
- WhatsApp bridge flows
- Feishu, DingTalk, QQ, email
- additional bridge-style and promoted adapters depending on configuration

## Beginner Mental Model

Each channel setup usually answers four questions:

1. How does Kabot authenticate to the platform?
2. Who is allowed to talk to the bot?
3. Which agent should receive those messages?
4. Does the platform need a local bridge or direct API access?

If you can answer those four clearly, channel setup becomes much easier.

## What Channels Need

Most channels need three things:
- credentials or bot token
- access control rules such as `allowFrom`
- optional binding to a specific agent

In practice, some channels also need:
- webhook or bridge health
- local background service availability
- per-channel message policy
- per-instance model or agent routing

## Recommended Setup Order

For a stable rollout, do this in order:

1. make sure `kabot agent -m "hello"` works first
2. start `kabot gateway`
3. connect one channel only
4. test one inbound message
5. test one outbound response
6. add `allowFrom`
7. only then add more channels or bots

## Use The Wizard First

```bash
kabot config
```

Then go into `Channels`.

This is the safest path for:
- adding one channel
- managing multiple instances
- setting `allowFrom`
- choosing per-bot AI routing

The wizard matters because it reduces:
- token leaks in prompts
- malformed manual JSON edits
- forgotten allow lists
- broken per-bot bindings

## Single-Bot vs Multi-Bot

### Single-Bot

Best when:
- you are just starting
- one persona is enough
- one model is enough
- the channel is personal use only

### Multi-Bot / Multi-Instance

Best when:
- different groups need different behavior
- one bot should be cheap and fast, another more capable
- you want strong separation between work and personal contexts
- you want different agents per channel or per chat surface

## Multi-Bot Setup

You can run multiple channel instances and bind them differently.

Examples:
- Telegram bot A -> work agent
- Telegram bot B -> personal agent
- WhatsApp bridge -> support agent

This is especially useful when each bot should have:
- a different model
- a different workspace
- a different role

## Channel Security Basics

The most important security field for most channel setups is `allowFrom`.

That field controls who may talk to the bot.

Examples:
- Telegram user IDs
- WhatsApp phone numbers
- allow-list style identities depending on the adapter

Good rule:
- personal toy bot: still use allow lists if possible
- shared or public deployment: treat allow lists as mandatory

## Platform Notes

### Telegram

Good first channel for most users because:
- setup is straightforward
- debugging is simple
- one-to-one testing is easy

Recommended use:
- direct personal bot
- operator testing
- first real-world smoke tests

### Discord

Good when:
- you want Kabot inside a community or team space
- mentions or channel workflows matter

Things to think about:
- permission scope
- channel visibility
- bot role placement

### Slack

Good for internal team workflows.

Pay attention to:
- bot token vs app token requirements
- DM policy
- group policy
- workspace restrictions

### WhatsApp

Usually the most operationally sensitive because it often depends on a local bridge.

Things to verify:
- bridge is reachable
- QR login succeeded
- bridge can stay alive in the background
- local machine can maintain that runtime

### Email / Bridge-Based Adapters

These often need a more careful operator mindset because they may involve:
- separate bridge health
- external auth systems
- more failure points than a single direct bot token

## Security Rules

For production or shared deployments:
- configure `allowFrom`
- audit who can reach each bot
- do not leave public channels open without a clear policy

Also consider:
- using dedicated agents per sensitive channel
- avoiding a single bot identity for everything
- using least-privilege gateway and operator tokens

## Agent Binding Strategy

Channel bindings become much easier to manage if you decide the role first.

Examples:

| Channel | Suggested Agent Role |
| --- | --- |
| Telegram personal bot | default personal agent |
| Discord community helper | moderation or community agent |
| Slack internal workspace | work or ops agent |
| WhatsApp support bot | support or triage agent |

## Testing Checklist

After configuring a channel, verify all of these:

1. credential saved
2. channel appears configured
3. one allowed sender can reach it
4. one blocked sender cannot reach it
5. the correct agent receives the message
6. the reply reaches the right place

## Common Problems

### The bot is silent

Check:
- credential validity
- gateway is running
- channel bridge is healthy
- `allowFrom` is not blocking you
- the binding points to the expected agent

### The wrong agent replies

Check:
- channel binding order
- default agent fallback
- instance-specific routing

### Messages are inconsistent

Check:
- whether multiple bots share one role accidentally
- whether one channel is bound to the wrong workspace
- whether bridge-based adapters are unstable

## Recommended Channel Rollout

1. Start with one channel.
2. Verify one real inbound and outbound message.
3. Add `allowFrom` restrictions.
4. Only then add extra bots or extra platforms.

## Related Pages

- [Configuration guide](configuration.md)
- [Multi-agent guide](multi-agent.md)
- [Gateway and dashboard guide](gateway-dashboard.md)
- [Security guide](security.md)
