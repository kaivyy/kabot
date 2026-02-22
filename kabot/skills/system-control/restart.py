import argparse
import os
import sys

# Add the project root to sys.path to allow imports from kabot
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from kabot.utils.restart import RestartManager


def main():
    parser = argparse.ArgumentParser(description="Restart the bot and save state.")
    parser.add_argument("--chat-id", help="Chat ID to notify after restart")
    parser.add_argument("--message", help="Message to send after restart")
    parser.add_argument("--channel", help="Channel (telegram/discord) to notify")

    args = parser.parse_args()

    print("Initiating restart sequence...")

    if args.chat_id and args.channel:
        print(f"Saving restart context: channel={args.channel}, chat_id={args.chat_id}")
        # Default message if not provided
        msg = args.message if args.message else "I'm back from the restart!"

        manager = RestartManager()
        manager.schedule_restart(
            chat_id=args.chat_id,
            channel=args.channel,
            message=msg
        )

    print("Exiting with code 42 (Restart)...")
    sys.exit(42)

if __name__ == "__main__":
    main()
