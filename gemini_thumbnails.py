#!/usr/bin/env python3
"""
Thumbnail selector + extractor using Google Gemini 2.5 Pro
Identifies 5–10 high-CTR moments and extracts frames via ffmpeg.
"""

import os
import sys
import argparse
from pathlib import Path
import google.generativeai as genai
import json
import re
import subprocess
import time
import random
import mimetypes
import threading
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded

from utils.progress import ProgressPrinter, human_bytes, human_rate, human_duration, initial_processing_estimate
from utils.paths import get_output_paths


def _format_hms(seconds: float) -> str:
    s = int(max(0, round(float(seconds))))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_time_to_seconds(ts):
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return float(ts)
        except Exception:
            return None
    if isinstance(ts, str):
        txt = ts.strip()
        try:
            return float(txt)
        except Exception:
            pass
        parts = txt.split(":")
        try:
            parts = [int(p) for p in parts]
        except ValueError:
            return None
        if len(parts) == 3:
            h, m, s = parts
        elif len(parts) == 2:
            h, m, s = 0, parts[0], parts[1]
        else:
            return None
        return float(h) * 3600 + float(m) * 60 + float(s)
    return None


def _extract_frame(video_path: str, ts_seconds: float, output_dir: Path, index: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    hms = _format_hms(ts_seconds)
    out_path = output_dir / f"thumb_{index:02d}_{hms.replace(':','-')}.jpg"
    # Fast seek before input; fallback tries after input if needed
    cmd = [
        "ffmpeg", "-ss", f"{ts_seconds}", "-i", str(video_path),
        "-frames:v", "1", "-q:v", "2", str(out_path), "-y"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        cmd = [
            "ffmpeg", "-i", str(video_path), "-ss", f"{ts_seconds}",
            "-frames:v", "1", "-q:v", "2", str(out_path), "-y"
        ]
        subprocess.run(cmd, capture_output=True, text=True)
    return out_path


def _parse_retry_delay(exc: Exception) -> float:
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
                         max_retries: int = 8, initial_delay: float = 5.0, backoff: float = 1.7) -> any:
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


def select_and_extract_thumbnails(video_path, api_key=None, output_root: Path = None, file_id: str = None, model_name: str = "models/gemini-2.5-pro"):
    # Configure API key
    if api_key:
        genai.configure(api_key=api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY environment variable")
        sys.exit(1)

    printer = ProgressPrinter()

    own_upload = True
    if file_id:
        try:
            video_file = genai.get_file(file_id)
        except Exception as e:
            print(f"Error retrieving file_id {file_id}: {e}")
            sys.exit(1)
        own_upload = False
        try:
            total_bytes = os.path.getsize(video_path)
        except Exception:
            total_bytes = 0
        elapsed = 0.0
        printer.println(f"Using existing uploaded file: {video_file.name}")
    else:
        print(f"Uploading video: {video_path}")
        # Upload video file with mime type and track timing
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
                est_total = max(est_total, elapsed_proc * 1.25)
            remaining = max(0.0, est_total - elapsed_proc)
            printer.update_line(f"Processing... (elapsed: {human_duration(elapsed_proc)}, est. {human_duration(remaining)} remaining)")
            time.sleep(1.0)
            video_file = genai.get_file(video_file.name)
        total_elapsed = time.monotonic() - start_time
        printer.println(f"Processing complete in {human_duration(total_elapsed)}")
    except KeyboardInterrupt:
        printer.println()
        raise

    if video_file.state.name == "FAILED":
        print(f"Video processing failed: {video_file.state}")
        sys.exit(1)

    print("Selecting thumbnails with Gemini 2.5 Pro...")

    # Create model
    model = genai.GenerativeModel(model_name)

    # Wrestling-focused thumbnail prompt
    thumb_prompt = """
Select 8–12 distinct, high-CTR moments in this wrestling/grappling video that would make compelling clickable thumbnails for gay male amateur grappling fans.

Prioritize these wrestling-specific moments:
- Pin attempts and near-falls with clear tension
- Tight chest-to-chest control positions
- Decisive takedowns with impact
- Dramatic scrambles showing athleticism  
- Submission threats with visible strain
- Victory poses, hand raises, or dominance displays
- Clear momentum swings or comebacks
- Intense face-to-face or body-to-body contact

Avoid:
- Motion blur, transitions, title cards, fades
- Near-duplicate moments (<3s apart)
- Poor lighting or unclear subjects

Return ONLY JSON with this exact schema:
{
  "thumbnails": [
    {
      "timestamp_seconds": number,
      "timestamp_hms": "HH:MM:SS",
      "reason": "why this frame works for wrestling fans",
      "suggested_caption": "<= 8 words",
      "label": "technical_exchange|dominance|comeback|submission_threat|near_fall|scramble|victory|control",
      "why_high_ctr": "brief hook for wrestling audience",
      "crop_hint": "faces|upper_bodies|full_body|grip_closeup"
    }
  ]
}
"""
    try:
        thumb_response = _generate_with_retry(
            model,
            [video_file, thumb_prompt],
            generation_config={"response_mime_type": "application/json", "temperature": 0.2}
        )

        candidates = []
        payload = None
        try:
            payload = json.loads(thumb_response.text)
        except Exception:
            m = re.search(r"\[[\s\S]*\]", thumb_response.text)
            if m:
                try:
                    payload = json.loads(m.group(0))
                except Exception:
                    payload = None
        # Normalize payload into list
        items = []
        if isinstance(payload, dict) and isinstance(payload.get("thumbnails"), list):
            items = payload["thumbnails"]
        elif isinstance(payload, list):
            items = payload

        for item in items:
            if not isinstance(item, dict):
                continue
            ts = _parse_time_to_seconds(item.get("timestamp_seconds"))
            if ts is None:
                ts = _parse_time_to_seconds(item.get("timestamp_hms") or item.get("timestamp"))
            if ts is None:
                continue
            candidates.append({
                "timestamp_seconds": float(ts),
                "timestamp_hms": _format_hms(ts),
                "reason": (item.get("reason") or "").strip(),
                "suggested_caption": (item.get("suggested_caption") or "").strip(),
                "label": (item.get("label") or "unknown").strip(),
                "why_high_ctr": (item.get("why_high_ctr") or "").strip(),
                "crop_hint": (item.get("crop_hint") or "full_body").strip()
            })

        # Deduplicate by keeping at most one candidate per rounded second
        # (e.g., 2.0s and 2.1s collapse to the same moment), and cap at 10.
        deduped = []
        seen_secs = set()
        for c in sorted(candidates, key=lambda x: x["timestamp_seconds"]):
            sec = int(round(c["timestamp_seconds"]))
            if sec in seen_secs:
                continue
            seen_secs.add(sec)
            deduped.append(c)
        if len(deduped) > 10:
            deduped = deduped[:10]

        paths = get_output_paths(video_path, output_root)
        thumbs_dir = paths["thumbnails_dir"]
        for idx, c in enumerate(deduped, 1):
            out = _extract_frame(video_path, c["timestamp_seconds"], thumbs_dir, idx)
            c["image_path"] = str(out)

        # Append wrestling-focused thumbnail section to analysis file
        analysis_file = paths["analysis_txt"]
        exists = analysis_file.exists()
        with open(analysis_file, 'a' if exists else 'w') as f:
            if not exists:
                f.write("GEMINI 2.5 PRO VIDEO ANALYSIS\n")
                f.write("=" * 60 + "\n\n")
            f.write("\n" + "=" * 60 + "\n")
            f.write("THUMBNAIL PICKS (WRESTLING)\n")
            f.write("=" * 60 + "\n\n")
            for c in deduped:
                cap = f" '{c['suggested_caption']}'" if c.get('suggested_caption') else ""
                label = f" [{c['label']}]" if c.get('label') else ""
                ctr_hook = f" — {c['why_high_ctr']}" if c.get('why_high_ctr') else ""
                crop = f" (crop: {c['crop_hint']})" if c.get('crop_hint') else ""
                f.write(f"[{c['timestamp_hms']}]{label} {c['image_path']}{cap}{ctr_hook}{crop}\n")

        # Save structured thumbnail data
        meta_file = paths["thumbnails_json"]
        with open(meta_file, 'w') as jf:
            json.dump({"thumbnails": deduped}, jf, indent=2)

        print(f"Extracted {len(deduped)} thumbnails to: {thumbs_dir}")
        print(f"Thumbnail metadata saved to: {meta_file}")
    finally:
        # Cleanup uploaded file
        try:
            if own_upload:
                genai.delete_file(video_file.name)
                print("Cleaned up uploaded video from Gemini")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Select and extract thumbnail candidates via Gemini 2.5 Pro"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--api-key",
        help="Google Gemini API key (or set GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--output-root",
        help="Optional root directory for outputs (default: current working directory)",
        default=None
    )
    parser.add_argument(
        "--model",
        default="models/gemini-2.5-pro",
        help="Model name to use (e.g., 'models/gemini-1.5-pro')"
    )
    parser.add_argument(
        "--file-id",
        help="Reuse an already uploaded Gemini file id (e.g., 'files/abc123'); skips local upload"
    )

    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    select_and_extract_thumbnails(
        args.video,
        api_key=args.api_key,
        output_root=Path(args.output_root) if args.output_root else None,
        file_id=args.file_id,
        model_name=args.model
    )


if __name__ == "__main__":
    main()
