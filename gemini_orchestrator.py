#!/usr/bin/env python3
"""
One-upload orchestrator: uploads once, then runs analyzer, thumbnails, and editing guide with the same Gemini file.
Default model: models/gemini-1.5-pro
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
import mimetypes
import time
import threading
import google.generativeai as genai
from utils.progress import ProgressPrinter, human_duration, human_rate, initial_processing_estimate


def main():
    parser = argparse.ArgumentParser(description="Upload once, run all processors with a single Gemini file")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--api-key", help="Gemini API key (or set GEMINI_API_KEY)")
    parser.add_argument("--model", default="models/gemini-1.5-pro", help="Model to use for all steps")
    parser.add_argument("--output-root", default=None, help="Optional root dir for outputs")
    parser.add_argument("--max-output-tokens", type=int, default=8000, help="Analyzer max output tokens")
    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    if args.api_key:
        genai.configure(api_key=args.api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY env var")
        sys.exit(1)

    printer = ProgressPrinter()

    # Upload once with heartbeat
    mime, _ = mimetypes.guess_type(args.video)
    if not mime:
        mime = "video/mp4"
    try:
        total_bytes = os.path.getsize(args.video)
    except Exception:
        total_bytes = 0
    up_start = time.monotonic()
    stop_event = threading.Event()
    def _hb():
        while not stop_event.is_set():
            printer.update_line(f"Uploading... (elapsed: {human_duration(time.monotonic() - up_start)})")
            time.sleep(1.0)
    t = threading.Thread(target=_hb, daemon=True)
    t.start()

    try:
        gfile = genai.upload_file(path=args.video, mime_type=mime, display_name=os.path.basename(args.video), resumable=True)
    finally:
        stop_event.set()
        try:
            t.join(timeout=1.0)
        except Exception:
            pass
        up_end = time.monotonic()
        elapsed = max(0.0, up_end - up_start)
        avg_rate = (total_bytes / elapsed) if elapsed > 0 else 0
        printer.println(f"Upload complete in {human_duration(elapsed)} at {human_rate(avg_rate)} avg")
        printer.println(f"Uploaded: {gfile.name}")

    # Processing ETA
    printer.println("Processing video...")
    est_total = initial_processing_estimate(total_bytes, upload_duration_s=elapsed)
    start = time.monotonic()
    while gfile.state.name == "PROCESSING":
        el = time.monotonic() - start
        if el >= est_total * 0.9:
            est_total = max(est_total, el * 1.25)
        rem = max(0.0, est_total - el)
        printer.update_line(f"Processing... (elapsed: {human_duration(el)}, est. {human_duration(rem)} remaining)")
        time.sleep(1.0)
        gfile = genai.get_file(gfile.name)

    if gfile.state.name == "FAILED":
        print(f"Video processing failed: {gfile.state}")
        sys.exit(1)

    printer.println(f"Processing complete in {human_duration(time.monotonic() - start)}")

    # Run processors with --file-id and model
    output_root_arg = ["--output-root", args.output_root] if args.output_root else []
    model_arg = ["--model", args.model]
    file_arg = ["--file-id", gfile.name]

    # Analyzer
    cmd = [sys.executable, "gemini_analyzer.py", args.video, "--max-output-tokens", str(args.max_output_tokens)] + model_arg + file_arg + output_root_arg
    print("Running analyzer:", " ".join(cmd))
    subprocess.run(cmd, check=False)

    # Thumbnails
    cmd = [sys.executable, "gemini_thumbnails.py", args.video] + model_arg + file_arg + output_root_arg
    print("Running thumbnails:", " ".join(cmd))
    subprocess.run(cmd, check=False)

    # Editing guide (optional: feed analyzer JSON if present)
    stem = Path(args.video).stem
    analysis_json = Path(args.output_root or Path.cwd()) / stem / "analysis" / f"{stem}_analysis.json"
    eg_args = []
    if analysis_json.exists():
        eg_args = ["--analysis-json", str(analysis_json)]
    cmd = [sys.executable, "gemini_editing_guide.py", args.video] + eg_args + model_arg + file_arg + output_root_arg
    print("Running editing guide:", " ".join(cmd))
    subprocess.run(cmd, check=False)

    # Cleanup uploaded file
    try:
        genai.delete_file(gfile.name)
        print("Cleaned up uploaded video from Gemini")
    except Exception:
        pass


if __name__ == "__main__":
    main()