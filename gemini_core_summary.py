#!/usr/bin/env python3
"""
Core Summary (Minute-by-Minute) using Google Gemini 2.5 Pro
Generates a detailed, minute-by-minute core summary for the entire video.
"""

import os
import sys
import argparse
import time
import random
import subprocess
from pathlib import Path
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded

from utils.progress import ProgressPrinter, human_duration, human_rate, initial_processing_estimate
from utils.paths import get_output_paths


def _parse_retry_delay(exc: Exception) -> float:
    import re
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


def get_video_duration_seconds(video_path: str) -> float:
    try:
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ], capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def _format_hms(seconds: float) -> str:
    s = int(max(0, round(float(seconds))))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_minute_by_minute_prompt(duration_seconds: float, start_s: int = None, end_s: int = None) -> str:
    total_m = int(max(1, round(duration_seconds / 60.0)))
    scope = "for the entire video"
    scope_extra = ""
    if start_s is not None and end_s is not None:
        scope = f"ONLY for the segment {_format_hms(start_s)}–{_format_hms(end_s)} (absolute timecodes)"
        scope_extra = f"\n- SCOPE: Cover strictly between {start_s}s and {end_s}s; timecodes must be absolute to the full video."
    return f"""You are a careful, neutral video analyst. Produce a detailed, minute-by-minute CORE SUMMARY {scope}.

REQUIREMENTS:
- COVERAGE: Provide end-to-end coverage from 00:00 to the end (about {total_m} minutes). Do not skip long lulls; mark them clearly.{scope_extra}
- FORMAT: Use headings per minute bucket and concise bullet points under each.
- DO NOT include any sales/marketing language. Keep it descriptive and neutral.

FORMAT EXACTLY:
For each minute m, write a section:
[MM:SS–MM:SS]
- Actions: key grappling/wrestling actions and transitions
- Positions: mount/side/control/standup, who is dominant
- Momentum: who leads (A/B/even) and any shifts
- Notes: notable behaviors (fatigue, taunting, resets), camera/clarity if relevant

AT THE END: add a short 2–3 bullet recap of the overall arc (no marketing).
"""


def main():
    parser = argparse.ArgumentParser(description="Generate minute-by-minute core summary with Gemini 2.5 Pro")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--api-key", help="Google Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--mime-type", help="Override MIME type (e.g., 'video/mp4')")
    parser.add_argument("--max-output-tokens", type=int, default=8192, help="Cap for model output length")
    parser.add_argument("--chunk-minutes", type=int, default=8, help="Segment size in minutes (0 = disabled; default 8)")
    parser.add_argument("--output-root", default=None, help="Optional root directory for outputs")

    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    # Configure API key
    if args.api_key:
        genai.configure(api_key=args.api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY environment variable")
        sys.exit(1)

    printer = ProgressPrinter()

    # Duration for prompt context
    duration_seconds = get_video_duration_seconds(args.video)

    # Detect MIME type
    import mimetypes
    mime_type = args.mime_type
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(args.video)
    if not mime_type:
        mime_type = "video/mp4"

    # Upload with heartbeat
    print(f"Uploading video to Gemini...")
    try:
        total_bytes = os.path.getsize(args.video)
    except Exception:
        total_bytes = 0

    upload_start = time.monotonic()
    import threading
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
            path=args.video,
            mime_type=mime_type,
            display_name=os.path.basename(args.video),
            resumable=True
        )
    except Exception as e:
        print(f"Error uploading video: {e}")
        sys.exit(1)
    finally:
        stop_event.set()
        try:
            hb_thread.join(timeout=1.0)
        except Exception:
            pass
        upload_end = time.monotonic()
        up_elapsed = max(0.0, upload_end - upload_start)
        avg_rate = (total_bytes / up_elapsed) if up_elapsed > 0 else 0
        printer.println(f"Upload complete in {human_duration(up_elapsed)} at {human_rate(avg_rate)} avg")
        printer.println(f"Uploaded: {video_file.name}")

    # Processing with ETA
    printer.println("Processing video...")
    est_total = initial_processing_estimate(total_bytes, upload_duration_s=up_elapsed)
    start_time = time.monotonic()
    while video_file.state.name == "PROCESSING":
        elapsed = time.monotonic() - start_time
        if elapsed >= est_total * 0.9:
            est_total = max(est_total, elapsed * 1.25)
        remaining = max(0.0, est_total - elapsed)
        printer.update_line(f"Processing... (elapsed: {human_duration(elapsed)}, est. {human_duration(remaining)} remaining)")
        time.sleep(1.0)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        print(f"Video processing failed: {video_file.state}")
        sys.exit(1)

    total_elapsed = time.monotonic() - start_time
    printer.println(f"Processing complete in {human_duration(total_elapsed)}")

    # Prompt and generation
    model = genai.GenerativeModel("models/gemini-2.5-pro")
    gen_config = {"max_output_tokens": int(args.max_output_tokens)} if args.max_output_tokens else None

    # Write header
    paths = get_output_paths(args.video, Path(args.output_root) if args.output_root else None)
    out_txt = paths["analysis_dir"] / f"{Path(args.video).stem}_core_summary.txt"
    with open(out_txt, 'w') as f:
        f.write("GEMINI 2.5 PRO — CORE SUMMARY (MINUTE-BY-MINUTE)\n")
        f.write("=" * 60 + "\n\n")

    try:
        if args.chunk_minutes and args.chunk_minutes > 0 and duration_seconds > 0:
            seg_len = max(60, args.chunk_minutes * 60)
            segments = []
            start = 0
            while start < duration_seconds:
                end = min(start + seg_len, duration_seconds)
                segments.append((int(start), int(end)))
                start = end
            for idx, (s, e) in enumerate(segments, 1):
                print(f"Generating segment {idx}/{len(segments)}: {_format_hms(s)}–{_format_hms(e)}")
                prompt = build_minute_by_minute_prompt(duration_seconds, start_s=s, end_s=e)
                response = _generate_with_retry(model, [video_file, prompt], generation_config=gen_config)
                with open(out_txt, 'a') as f:
                    f.write("-" * 60 + "\n")
                    f.write(f"SEGMENT {idx}: {_format_hms(s)}–{_format_hms(e)}\n")
                    f.write("-" * 60 + "\n\n")
                    f.write(response.text + "\n\n")
        else:
            prompt = build_minute_by_minute_prompt(duration_seconds)
            response = _generate_with_retry(model, [video_file, prompt], generation_config=gen_config)
            with open(out_txt, 'a') as f:
                f.write(response.text)
    except Exception as e:
        print(f"Error generating summary: {e}")
        sys.exit(1)
    finally:
        try:
            genai.delete_file(video_file.name)
            print("Cleaned up uploaded video from Gemini")
        except Exception:
            pass

    print(f"\nCore summary saved to: {out_txt}")


if __name__ == "__main__":
    main()