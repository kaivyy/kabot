#!/usr/bin/env python3
"""
Speech-to-Text (STT) script using OpenAI Whisper.
"""
import argparse
import os
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: 'openai' package is required. Install with: pip install openai")
    sys.exit(1)

def transcribe_audio(audio_path):
    """Transcribe audio file to text."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    path = Path(audio_path)
    if not path.exists():
        print(f"Error: Audio file not found at {audio_path}")
        sys.exit(1)

    print(f"👂 Listening to {path.name}...")

    try:
        with open(path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )

        print("\n--- Transcript ---\n")
        print(transcript)
        print("\n------------------")
        return transcript

    except Exception as e:
        print(f"Error transcribing audio: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio to text")
    parser.add_argument("audio_path", help="Path to audio file")
    args = parser.parse_args()

    transcribe_audio(args.audio_path)
