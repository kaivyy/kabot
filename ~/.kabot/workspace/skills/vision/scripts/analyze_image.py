#!/usr/bin/env python3
"""
Vision Analysis Script for Kabot.
Uses LiteLLM to send images to multimodal models.
"""
import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path

# Try to import litellm, fail gracefully if not installed
try:
    from litellm import completion
except ImportError:
    print("Error: 'litellm' package is required. Install with: pip install litellm")
    sys.exit(1)

def encode_image(image_path):
    """Encode image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_image(image_path: str, prompt: str = "Describe this image", model: str = None):
    """Analyze image using a multimodal model."""

    # 1. Determine Model (Auto-select best available)
    if not model:
        if os.environ.get("OPENAI_API_KEY"):
            model = "gpt-4o"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            model = "claude-3-5-sonnet-20240620"
        elif os.environ.get("GEMINI_API_KEY"):
            model = "gemini/gemini-1.5-pro"
        else:
            print("Error: No API key found for OpenAI, Anthropic, or Gemini.")
            sys.exit(1)

    print(f"👁️ Analyzing image with {model}...")

    # 2. Prepare Content
    content = []

    # Check if URL or Local File
    if image_path.startswith("http"):
        content.append({
            "type": "image_url",
            "image_url": {"url": image_path}
        })
    else:
        path = Path(image_path)
        if not path.exists():
            print(f"Error: File not found at {image_path}")
            sys.exit(1)

        # Get mime type
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg" # Default

        base64_image = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
        })

    # Add text prompt
    content.append({"type": "text", "text": prompt})

    # 3. Call API
    try:
        response = completion(
            model=model,
            messages=[
                {"role": "user", "content": content}
            ],
            max_tokens=1024
        )
        print("\n--- Analysis Result ---\n")
        print(response.choices[0].message.content)
        print("\n-----------------------")

    except Exception as e:
        print(f"Error calling Vision API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze images with AI")
    parser.add_argument("image_path", help="Path to image file or URL")
    parser.add_argument("--prompt", default="Describe this image in detail.", help="Question about the image")
    parser.add_argument("--model", help="Specific model to use")

    args = parser.parse_args()
    analyze_image(args.image_path, args.prompt, args.model)
