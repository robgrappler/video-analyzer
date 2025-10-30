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
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded


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


def select_and_extract_thumbnails(video_path, api_key=None):
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

    print("Selecting thumbnails with Gemini 2.5 Pro...")

    # Create model
    model = genai.GenerativeModel("models/gemini-2.5-pro")

    # Prompt for thumbnails
    thumb_prompt = """
Select 5–10 distinct, high-CTR moments in this video that would make compelling clickable thumbnails.
Guidelines:
- Prefer peak action or reaction moments where the primary subject is clear, sharp, and well-lit.
- Avoid motion blur, transitions, title cards, fades, or near-duplicate moments (<3s apart).
- Spread selections across the video if possible.
Return ONLY JSON with this exact schema:
{
  "thumbnails": [
    {
      "timestamp_seconds": number,           // nearest whole second if unsure
      "timestamp_hms": "HH:MM:SS",          // zero-padded
      "reason": "why this frame works",
      "suggested_caption": "<= 8 words"
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
                "suggested_caption": (item.get("suggested_caption") or "").strip()
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

        thumbs_dir = Path(video_path).parent / f"{Path(video_path).stem}_thumbnails"
        for idx, c in enumerate(deduped, 1):
            out = _extract_frame(video_path, c["timestamp_seconds"], thumbs_dir, idx)
            c["image_path"] = str(out)

        # Append thumbnail section to analysis file (create if missing)
        output_file = Path(video_path).stem + "_gemini_analysis.txt"
        exists = Path(output_file).exists()
        with open(output_file, 'a' if exists else 'w') as f:
            if not exists:
                f.write("GEMINI 2.5 PRO VIDEO ANALYSIS\n")
                f.write("=" * 60 + "\n\n")
            f.write("\n" + "=" * 60 + "\n")
            f.write("THUMBNAIL CANDIDATES\n")
            f.write("=" * 60 + "\n\n")
            for c in deduped:
                cap = f" {c['suggested_caption']}" if c.get('suggested_caption') else ""
                reason = f" — {c['reason']}" if c.get('reason') else ""
                f.write(f"[{c['timestamp_hms']}] {c['image_path']}{cap}{reason}\n")

        # Save structured thumbnail data
        meta_file = Path(video_path).stem + "_thumbnails.json"
        with open(meta_file, 'w') as jf:
            json.dump({"thumbnails": deduped}, jf, indent=2)

        print(f"Extracted {len(deduped)} thumbnails to: {thumbs_dir}")
        print(f"Thumbnail metadata saved to: {meta_file}")
    finally:
        # Cleanup uploaded file
        try:
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

    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    select_and_extract_thumbnails(args.video, api_key=args.api_key)


if __name__ == "__main__":
    main()
