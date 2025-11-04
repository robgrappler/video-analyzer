#!/usr/bin/env python3
"""
Transcription generator using Google Gemini
Generates SRT format transcription in Mexican Spanish
"""

import os
import sys
import argparse
from pathlib import Path
import google.generativeai as genai
import re
import time
import random
import mimetypes
import threading
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded

from utils.progress import ProgressPrinter, human_bytes, human_rate, human_duration, initial_processing_estimate
from utils.paths import get_output_paths


def _parse_retry_delay(exc: Exception) -> float:
    """Try to parse server-suggested retry delay (seconds) from exception text; return -1 if none."""
    s = str(exc)
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
                         max_retries: int = 8, initial_delay: float = 5.0, backoff: float = 1.7):
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
            print(f"Rate limit hit (attempt {attempt}/{max_retries}). Retrying in {wait:.1f}s...", file=sys.stderr)
            time.sleep(wait)
            delay *= backoff
            continue
        except (ServiceUnavailable, DeadlineExceeded) as e:
            attempt += 1
            if attempt > max_retries:
                raise
            wait = delay * (1.0 + random.uniform(0.05, 0.25))
            print(f"Transient error (attempt {attempt}/{max_retries}). Retrying in {wait:.1f}s...", file=sys.stderr)
            time.sleep(wait)
            delay *= backoff
            continue


def _validate_srt_format(content: str) -> bool:
    """Basic validation that content looks like SRT format."""
    lines = content.strip().split('\n')
    if len(lines) < 3:
        return False
    
    # Check for sequence number at start
    try:
        int(lines[0].strip())
    except ValueError:
        return False
    
    # Check for timecode format (HH:MM:SS,mmm --> HH:MM:SS,mmm)
    timecode_pattern = r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}'
    if not re.search(timecode_pattern, lines[1]):
        return False
    
    return True


def generate_transcription(video_path, api_key=None, output_root: Path = None, 
                          file_id: str = None, model_name: str = "models/gemini-2.5-flash",
                          max_output_tokens: int = 8000):
    """Generate Mexican Spanish SRT transcription using Gemini."""
    
    # Configure API key
    if api_key:
        genai.configure(api_key=api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    printer = ProgressPrinter()
    
    # Get output paths
    paths = get_output_paths(video_path, output_root)
    transcription_dir = paths['base_dir'] / 'transcription'
    transcription_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = transcription_dir / f"{paths['stem']}_transcription_es.srt"

    own_upload = True
    if file_id:
        try:
            video_file = genai.get_file(file_id)
        except Exception as e:
            print(f"Error retrieving file_id {file_id}: {e}", file=sys.stderr)
            sys.exit(1)
        own_upload = False
        try:
            total_bytes = os.path.getsize(video_path)
        except Exception:
            total_bytes = 0
        elapsed = 0.0
        printer.println(f"Using existing uploaded file: {video_file.name}")
    else:
        printer.println(f"Uploading video: {video_path}")
        mime_type, _ = mimetypes.guess_type(video_path)
        try:
            total_bytes = os.path.getsize(video_path)
        except Exception:
            total_bytes = 0

        upload_start = time.monotonic()

        # Heartbeat to show upload activity
        stop_event = threading.Event()
        def _heartbeat():
            while not stop_event.is_set():
                elapsed_hb = time.monotonic() - upload_start
                printer.update_line(f"Uploading... (elapsed: {human_duration(elapsed_hb)})")
                time.sleep(1.0)
        hb_thread = threading.Thread(target=_heartbeat, daemon=True)
        hb_thread.start()

        try:
            video_file = genai.upload_file(
                path=video_path,
                mime_type=mime_type or "video/mp4",
                display_name=os.path.basename(video_path),
                resumable=True
            )
        finally:
            stop_event.set()
            try:
                hb_thread.join(timeout=1.0)
            except Exception:
                pass
            upload_end = time.monotonic()
            elapsed = max(0.0, upload_end - upload_start)
            avg_speed = (total_bytes / elapsed) if elapsed > 0 else 0
            printer.println(f"Upload complete in {human_duration(elapsed)} at {human_rate(avg_speed)} avg")

        printer.println(f"Uploaded: {video_file.name}")
    
    printer.println("Processing video...")

    # Wait for processing with ETA
    est_total = initial_processing_estimate(total_bytes, upload_duration_s=elapsed)
    start_time = time.monotonic()
    try:
        while video_file.state.name == "PROCESSING":
            elapsed_proc = time.monotonic() - start_time
            if elapsed_proc >= est_total * 0.9:
                est_total = elapsed_proc / 0.7
            remaining = max(0, est_total - elapsed_proc)
            printer.update_line(f"Processing... (elapsed: {human_duration(elapsed_proc)}, est. {human_duration(remaining)} remaining)")
            time.sleep(3.0)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            print(f"Video processing failed: {video_file.state.name}", file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:
        printer.println("\nInterrupted by user")
        sys.exit(1)
    
    elapsed_proc = time.monotonic() - start_time
    printer.println(f"Processing complete in {human_duration(elapsed_proc)}")

    # Create prompt for transcription
    prompt = f"""Transcribe this video's audio to Mexican Spanish in SRT subtitle format.

Requirements:
- Use proper SRT format with sequence numbers, timecodes, and subtitle text
- Timecodes must be in format: HH:MM:SS,mmm --> HH:MM:SS,mmm
- Capture ALL spoken dialogue and important audio cues
- Use Mexican Spanish vocabulary, slang, and expressions
- Keep subtitle segments short (max 2 lines, ~42 chars per line for readability)
- Ensure accurate timing that matches the speech
- Number each subtitle entry sequentially starting from 1

Example SRT format:
1
00:00:00,000 --> 00:00:03,500
Primera línea del subtítulo

2
00:00:03,500 --> 00:00:07,200
Segunda línea del subtítulo

Output ONLY the SRT content, no explanations or additional text."""

    printer.println("Generating transcription...")
    
    # Initialize model and generate
    model = genai.GenerativeModel(model_name=model_name)
    
    generation_config = genai.types.GenerationConfig(
        temperature=0.2,  # Lower temperature for more consistent transcription
        max_output_tokens=max_output_tokens
    )

    try:
        response = _generate_with_retry(
            model,
            [video_file, prompt],
            generation_config=generation_config
        )
    except Exception as e:
        print(f"Error generating transcription: {e}", file=sys.stderr)
        if own_upload:
            try:
                genai.delete_file(video_file.name)
            except Exception:
                pass
        sys.exit(1)

    # Extract and validate transcription
    try:
        transcription = response.text
    except Exception as e:
        print(f"Error extracting response text: {e}", file=sys.stderr)
        if own_upload:
            try:
                genai.delete_file(video_file.name)
            except Exception:
                pass
        sys.exit(1)

    # Basic validation
    if not _validate_srt_format(transcription):
        print("Warning: Generated content may not be valid SRT format", file=sys.stderr)

    # Save transcription
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(transcription)
        printer.println(f"\nTranscription saved to: {output_file}")
    except Exception as e:
        print(f"Error saving transcription: {e}", file=sys.stderr)
        if own_upload:
            try:
                genai.delete_file(video_file.name)
            except Exception:
                pass
        sys.exit(1)

    # Cleanup uploaded file if we uploaded it
    if own_upload:
        try:
            genai.delete_file(video_file.name)
            printer.println(f"Deleted uploaded file: {video_file.name}")
        except Exception as e:
            print(f"Warning: Could not delete uploaded file: {e}", file=sys.stderr)

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate Mexican Spanish SRT transcription using Google Gemini"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--api-key", help="Google Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--output-root", type=Path, help="Root directory for outputs (default: video directory)")
    parser.add_argument("--file-id", help="Reuse already-uploaded Gemini file ID to skip upload")
    parser.add_argument("--model", default="models/gemini-2.5-flash", 
                       help="Gemini model to use (default: models/gemini-2.5-flash)")
    parser.add_argument("--max-output-tokens", type=int, default=8000,
                       help="Maximum output tokens for transcription (default: 8000)")
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)
    
    output_file = generate_transcription(
        video_path=video_path,
        api_key=args.api_key,
        output_root=args.output_root,
        file_id=args.file_id,
        model_name=args.model,
        max_output_tokens=args.max_output_tokens
    )
    
    print(f"\n✓ Transcription complete: {output_file}")


if __name__ == "__main__":
    main()
