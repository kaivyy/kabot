#!/usr/bin/env python3
"""
Text-to-Speech (TTS) script using OpenAI TTS.
"""
import sys
import argparse
import os
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: 'openai' package is required. Install with: pip install openai")
    sys.exit(1)

def text_to_speech(text, output_path="speech.mp3", voice="alloy"):
    """Convert text to speech audio."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    print(f"🗣️ Speaking: '{text[:50]}...'")

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )

        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        response.stream_to_file(output_path)
        print(f"✅ Audio saved to: {output_path}")

    except Exception as e:
        print(f"Error generating speech: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert text to speech")
    parser.add_argument("text", help="Text to speak")
    parser.add_argument("--output", default="speech.mp3", help="Output file path")
    parser.add_argument("--voice", default="alloy", help="Voice ID (alloy, echo, fable, onyx, nova, shimmer)")

    args = parser.parse_args()
    text_to_speech(args.text, args.output, args.voice)
