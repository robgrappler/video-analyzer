#!/usr/bin/env python3
"""
Video Analyzer using Google Gemini 2.5 Pro
Analyzes full videos natively without frame extraction
"""

import os
import sys
import argparse
from pathlib import Path
import google.generativeai as genai
import re
import time
import random
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded


def _parse_retry_delay(exc: Exception) -> float:
    """Try to parse server-suggested retry delay (seconds) from exception text; return -1 if none."""
    s = str(exc)
    # Patterns seen in errors:
    # "Please retry in 4.444884096s." OR protobuf-like retry_delay { seconds: 4 }
    m = re.search(r"retry in\s+([0-9]+\.?[0-9]*)s", s, flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    m = re.search(r"retry_delay\s*\{\s*seconds:\s*([0-9]+)\s*\}", s, flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return -1.0


def _generate_with_retry(model, parts, generation_config=None, safety_settings=None,
                         max_retries: int = 8, initial_delay: float = 5.0, backoff: float = 1.7) -> any:
    """Call model.generate_content with retries on rate limits and transient errors."""
    attempt = 0
    delay = max(0.5, initial_delay)
    while True:
        try:
            return model.generate_content(parts, generation_config=generation_config, safety_settings=safety_settings)
        except ResourceExhausted as e:
            attempt += 1
            if attempt > max_retries:
                raise
            suggested = _parse_retry_delay(e)
            wait = suggested if suggested > 0 else delay
            wait *= (1.0 + random.uniform(0.05, 0.25))
            print(f"Rate limit hit (attempt {attempt}/{max_retries}). Retrying in {wait:.1f}s...")
            time.sleep(wait)
            delay *= backoff
            continue
        except (ServiceUnavailable, DeadlineExceeded) as e:
            attempt += 1
            if attempt > max_retries:
                raise
            wait = delay * (1.0 + random.uniform(0.05, 0.25))
            print(f"Transient error (attempt {attempt}/{max_retries}). Retrying in {wait:.1f}s...")
            time.sleep(wait)
            delay *= backoff
            continue


def analyze_video_gemini(video_path, api_key=None):
    """Analyze video with Gemini 2.5 Pro"""

    # Configure API key
    if api_key:
        genai.configure(api_key=api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY environment variable")
        sys.exit(1)

    print(f"Uploading video: {video_path}")

    # Upload video file
    video_file = genai.upload_file(path=video_path)
    print(f"Uploaded: {video_file.name}\nProcessing video...")

    # Wait for processing
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        print(f"Video processing failed: {video_file.state}")
        sys.exit(1)

    print("Analyzing video with Gemini 2.5 Pro...")

    # Create model
    model = genai.GenerativeModel("models/gemini-2.5-pro")

    # Analyze video
    prompt = """Analyze this video thoroughly and provide:

1. **Overall Summary**: What happens in the video from start to finish
2. **Key Scenes**: Describe the main scenes and transitions
3. **People/Subjects**: Who or what is featured
4. **Actions**: What activities or events occur
5. **Setting**: Where does this take place
6. **Tone/Style**: The mood and presentation style

Be detailed, direct, and descriptive."""

    try:
        response = _generate_with_retry(model, [video_file, prompt])

        print("\n" + "=" * 60)
        print("VIDEO ANALYSIS")
        print("=" * 60 + "\n")
        print(response.text)

        # Save analysis
        output_file = Path(video_path).stem + "_gemini_analysis.txt"
        with open(output_file, 'w') as f:
            f.write("GEMINI 2.5 PRO VIDEO ANALYSIS\n")
            f.write("=" * 60 + "\n\n")
            f.write(response.text)

        print(f"\n\nAnalysis saved to: {output_file}")
    finally:
        # Cleanup uploaded file
        try:
            genai.delete_file(video_file.name)
            print("Cleaned up uploaded video from Gemini")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Analyze videos with Google Gemini 2.5 Pro"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--api-key",
        help="Google Gemini API key (or set GEMINI_API_KEY env var)"
    )

    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    analyze_video_gemini(args.video, api_key=args.api_key)


if __name__ == "__main__":
    main()

