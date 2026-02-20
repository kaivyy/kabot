# Discord Action Examples

Detailed examples for complex Discord actions.

## Presence & Activity Details

Discord bots can only set `name`, `state`, `type`, and `url` on an activity.

### How fields render by activity type:

- **playing, streaming, listening, watching, competing**: `activityName` is shown in the sidebar under the bot's name (e.g. "**with fire**" for type "playing" and name "with fire"). `activityState` is shown in the profile flyout.
- **custom**: `activityName` is ignored. Only `activityState` is displayed as the status text in the sidebar.
- **streaming**: `activityUrl` may be displayed or embedded by the client.

### Examples:

**Set playing status:**
```json
{
  "action": "setPresence",
  "activityType": "playing",
  "activityName": "with fire"
}
```

**With state:**
```json
{
  "action": "setPresence",
  "activityType": "playing",
  "activityName": "My Game",
  "activityState": "In the lobby"
}
```

**Set a custom status (text in sidebar):**
```json
{
  "action": "setPresence",
  "activityType": "custom",
  "activityState": "Vibing"
}
```

## Channel Management

**Create a text channel:**
```json
{
  "action": "channelCreate",
  "guildId": "999",
  "name": "general-chat",
  "type": 0,
  "parentId": "888",
  "topic": "General discussion"
}
```

**Move a channel:**
```json
{
  "action": "channelMove",
  "guildId": "999",
  "channelId": "123",
  "parentId": "888",
  "position": 2
}
```

## Message Search & Pins

**Search messages:**
```json
{
  "action": "searchMessages",
  "guildId": "999",
  "content": "release notes",
  "channelIds": ["123", "456"],
  "limit": 10
}
```
