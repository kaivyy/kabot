# System Control Skill

This skill allows the agent to restart or shut down the bot.

## Commands

### Restart
Restart the bot. This is useful when the bot needs to reload code, clear memory, or recover from an unstable state.
The bot will exit with code 42, which should be handled by the supervisor/watchdog to trigger a restart.

Usage:
```bash
python -m kabot.skills.system-control.restart --chat-id <CHAT_ID> --message "I'm back!" --channel <telegram|discord>
```

Arguments:
- `--chat-id`: The ID of the chat where the bot should send a message after restarting.
- `--message`: The text message to send after restart.
- `--channel`: The platform channel (e.g., 'telegram', 'discord').

### Shutdown
Shut down the bot completely.

Usage:
```bash
python -m kabot.skills.system-control.shutdown
```
