---
name: discord
description: Control Discord via the discord tool: manage messages, reactions, polls, channels, and bot presence.
metadata: {"kabot":{"emoji":"🎮","requires":{"config":["channels.discord"]}}}
---

# Discord Actions

## Overview

Use `discord` to manage messages, reactions, threads, polls, and moderation. The tool uses the bot token configured for OpenClaw.

For detailed writing style guidelines, see [references/STYLE_GUIDE.md](references/STYLE_GUIDE.md).
For more complex examples, see [references/EXAMPLES.md](references/EXAMPLES.md).

## Actions

### Messaging & Reactions
- `sendMessage`: Send text/media to `to: "channel:<id>"` or `to: "user:<id>"`.
- `editMessage`, `deleteMessage`: Modify existing messages.
- `readMessages`, `fetchMessage`: Retrieve messages.
- `react`: Add emoji reaction.
- `reactions`: List reactions on a message.

### Interaction & Content
- `sticker`: Send stickers.
- `poll`: Create polls (2-10 answers).
- `emojiUpload`, `stickerUpload`: Add assets to a guild (requires guildId).
- `emojiList`: List custom emojis in a guild.

### Management & Info
- `permissions`: Check bot permissions in a channel.
- `memberInfo`, `roleInfo`, `channelInfo`, `channelList`: Fetch metadata.
- `voiceStatus`: Check user voice status.
- `eventList`: List scheduled events.

### Threads & Pins
- `threadCreate`, `threadList`, `threadReply`: Manage message threads.
- `pinMessage`, `listPins`: Manage pinned messages.

### Channel Management (Admin)
Requires `discord.actions.channels: true`.
- `channelCreate`, `channelEdit`, `channelDelete`, `channelMove`.
- `categoryCreate`, `categoryEdit`, `categoryDelete`.

### Bot Presence
Requires `discord.actions.presence: true`.
- `setPresence`: Set status (`online`, `dnd`, etc.) and activity (`playing`, `listening`, `watching`, `custom`).

## Action Gating
Enable/disable features via `discord.actions.*` config. Moderation, Roles, Channels, and Presence are disabled by default.

## Usage Note
- Use `to: "channel:<id>"` for sending messages.
- Use `channelId` directly for most other actions.
- Media attachments support `file:///` and `https://` URLs.
