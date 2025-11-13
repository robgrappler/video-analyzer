#!/usr/bin/env python3
"""
Wrestling Highlights Selector using Google Gemini 2.5 Pro
Identifies 10 high-converting promo-ready highlight moments (5s segments each)
with timestamps in seconds, frames, and HH:MM:SS format.
"""

import os
import sys
import argparse
import json
import subprocess
import time
import random
import re
import threading
import mimetypes
from pathlib import Path
from typing import Tuple, Dict, List, Any

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded

from utils.progress import ProgressPrinter, human_bytes, human_rate, human_duration, initial_processing_estimate
from utils.paths import get_output_paths


def _parse_retry_delay(exc: Exception) -> float:
    """Parse server-suggested retry delay from exception text."""
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


def _generate_with_retry(model, parts, generation_config=None, max_retries: int = 6, 
                         initial_delay: float = 5.0, backoff: float = 1.7) -> Any:
    """Call model.generate_content with retries on rate limits and transient errors."""
    attempt = 0
    delay = max(0.5, initial_delay)
    while True:
        try:
            return model.generate_content(parts, generation_config=generation_config)
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


def _format_hms(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    s = int(max(0, round(float(seconds))))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def probe_video_metadata(video_path: str) -> Tuple[float, float]:
    """
    Probe video for FPS and duration using ffprobe.
    Returns (fps, duration_seconds).
    """
    try:
        # Get FPS
        fps_output = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=avg_frame_rate",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        
        # Parse avg_frame_rate (e.g., "30000/1001" or "30/1")
        if "/" in fps_output:
            num, den = map(float, fps_output.split("/"))
            fps = num / den if den != 0 else 30.0
        else:
            fps = float(fps_output) if fps_output else 30.0
    except Exception as e:
        print(f"Error detecting FPS: {e}", file=sys.stderr)
        fps = 30.0
    
    try:
        # Get duration
        duration_output = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        duration = float(duration_output) if duration_output else 0.0
    except Exception as e:
        print(f"Error detecting duration: {e}", file=sys.stderr)
        duration = 0.0
    
    if duration <= 0:
        print("Error: Could not determine video duration")
        sys.exit(1)
    
    return fps, duration


def upload_or_get_file(video_path: str, file_id: str = None, printer: ProgressPrinter = None):
    """
    Upload video or reuse existing file_id.
    Returns (file_object, own_upload_bool, upload_duration_seconds, file_size_bytes).
    """
    if printer is None:
        printer = ProgressPrinter()
    
    own_upload = True
    total_bytes = 0
    elapsed = 0.0
    
    try:
        total_bytes = os.path.getsize(video_path)
    except Exception:
        total_bytes = 0
    
    if file_id:
        try:
            video_file = genai.get_file(file_id)
            own_upload = False
            printer.println(f"Using existing uploaded file: {video_file.name}")
            return video_file, own_upload, 0.0, total_bytes
        except Exception as e:
            print(f"Error retrieving file_id {file_id}: {e}")
            sys.exit(1)
    
    print(f"Uploading video: {video_path}")
    mime_type, _ = mimetypes.guess_type(video_path)
    if not mime_type:
        mime_type = "video/mp4"
    
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
            mime_type=mime_type,
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
    return video_file, own_upload, elapsed, total_bytes


def load_marketing_guide() -> str:
    """Load wrestling marketing guide or return fallback summary."""
    guide_path = Path(__file__).parent / "docs" / "WRESTLING_MARKETING_GUIDE.md"
    try:
        with open(guide_path, 'r') as f:
            content = f.read()
            if len(content) > 8000:
                lines = content.split('\n')
                key_sections = []
                in_relevant = False
                for line in lines:
                    if any(keyword in line.lower() for keyword in ['psychological hooks', 'intensity', 'dominance', 'drama', 'technical', 'conversion']):
                        in_relevant = True
                    if in_relevant:
                        key_sections.append(line)
                        if len('\n'.join(key_sections)) > 4000:
                            break
                return '\n'.join(key_sections)
            return content
    except FileNotFoundError:
        return """Wrestling Marketing Psychology (Summary):
- Intensity & Drama: Emphasize tension, near-falls, momentum shifts
- Dominance & Power: Highlight control positions, submission threats, victory poses
- Technical Mastery: Showcase clean technique, difficult holds, wrestling IQ
- Physical Appeal: Athletic conditioning, sweat/sheen, close contact
- Narrative Arc: Opening impact, mid-match swings, decisive finish
- Buyer Hooks: Competitiveness, chemistry, rewatchability"""


def build_prompt(guide_text: str, duration_seconds: float, fps: float, stem: str) -> str:
    """Build the Gemini prompt for highlight extraction."""
    duration_hms = _format_hms(duration_seconds)
    
    prompt = f"""You are a wrestling video analyst specializing in identifying high-conversion promotional moments for gay male amateur grappling fans.

VIDEO METADATA:
- Duration: {duration_hms} ({duration_seconds:.1f} seconds)
- Frame rate: {fps:.2f} FPS
- Source: {stem}

MARKETING PSYCHOLOGY FOUNDATION:
{guide_text}

YOUR TASK:
Identify exactly 10 distinct, non-overlapping highlight moments suitable for promotional intros or teaser clips. Each highlight should:
1. Be approximately 5 seconds long (acceptable range: 4.5–5.5 seconds)
2. Be at least 2 seconds apart from other highlights
3. Showcase one of these conversion-driving moment types:
   - Pin attempts and near-falls (dramatic tension)
   - Takedowns with visible impact (power display)
   - Submission threats or setups (suspense)
   - Dominant control positions (alpha energy)
   - Victory poses or hand raises (payoff)
   - Momentum shifts and comebacks (narrative arc)
   - Technical exchanges (wrestling skill)
   - Intense scrambles (athleticism/excitement)

PRIORITIZATION:
- Emphasize moments that would hook wrestling buyers in a 10-second promo reel
- Avoid transitions, fades, title cards, motion blur, or unclear action
- Prefer moments with clear, visible action and high emotional impact
- Center each segment on the peak action moment

RESPONSE FORMAT:
Return ONLY valid JSON (no prose) matching this exact schema:
{{
  "highlights": [
    {{
      "label": "dominance|technical_exchange|comeback|submission_threat|near_fall|scramble|victory|control|takedown",
      "start_seconds": <number>,
      "end_seconds": <number>,
      "why_high_converting": "<explanation referencing marketing psychology>",
      "emotional_hook": "<one-sentence hook for buyers>",
      "suggested_caption": "<max 8 words>"
    }}
  ]
}}

CONSTRAINTS:
- Exactly 10 highlights
- Non-overlapping with ≥2 seconds between segments
- All timestamps within [0, {duration_seconds:.1f}]
- Each highlight is 4.5–5.5 seconds
- Do NOT include frame numbers or HH:MM:SS; those will be computed
- Return ONLY the JSON object; no markdown, no prose"""

    return prompt


def parse_and_validate(raw_text: str, duration_seconds: float) -> List[Dict[str, Any]]:
    """Parse JSON response and validate highlight items."""
    text = raw_text.strip()
    
    # Strip code fences
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0]
    elif '```' in text:
        text = text.split('```')[1].split('```')[0]
    
    # Find JSON bounds
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end+1]
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parse failed: {e}", file=sys.stderr)
        return []
    
    if "highlights" not in data or not isinstance(data["highlights"], list):
        print("Warning: No 'highlights' list in response", file=sys.stderr)
        return []
    
    allowed_labels = {
        "dominance", "technical_exchange", "comeback", "submission_threat",
        "near_fall", "scramble", "victory", "control", "takedown"
    }
    
    items = []
    for item in data["highlights"]:
        try:
            label = str(item.get("label", "")).strip().lower()
            if label not in allowed_labels:
                label = "technical_exchange"
            
            start_s = float(item.get("start_seconds", 0))
            end_s = float(item.get("end_seconds", 0))
            
            if start_s > end_s:
                start_s, end_s = end_s, start_s
            
            start_s = max(0.0, min(start_s, duration_seconds))
            end_s = max(start_s, min(end_s, duration_seconds))
            
            if end_s - start_s < 0.5:
                end_s = min(start_s + 5.0, duration_seconds)
            
            items.append({
                "label": label,
                "start_seconds": start_s,
                "end_seconds": end_s,
                "why_high_converting": str(item.get("why_high_converting", "")).strip(),
                "emotional_hook": str(item.get("emotional_hook", "")).strip(),
                "suggested_caption": str(item.get("suggested_caption", "")).strip()[:50]
            })
        except Exception as e:
            print(f"Warning: Skipping invalid item: {e}", file=sys.stderr)
            continue
    
    return items


def normalize_highlights(items: List[Dict[str, Any]], duration_seconds: float) -> List[Dict[str, Any]]:
    """
    Normalize highlights: enforce ~5s duration, remove overlaps, maintain 2s spacing.
    """
    if not items:
        return []
    
    # Sort by start time
    items = sorted(items, key=lambda x: x["start_seconds"])
    
    normalized = []
    for item in items:
        start = item["start_seconds"]
        end = item["end_seconds"]
        duration = end - start
        
        # Adjust to ~5s if outside acceptable range
        if duration < 4.5 or duration > 5.5:
            end = min(start + 5.0, duration_seconds)
        
        # Check for overlap/spacing with existing
        overlap = False
        for prev in normalized:
            # At least 2s between segments
            if start < prev["end_seconds"] + 2.0 and end > prev["start_seconds"] - 2.0:
                overlap = True
                break
        
        if not overlap:
            normalized.append({
                **item,
                "start_seconds": start,
                "end_seconds": end
            })
    
    # If we have fewer than 10, we'll still return what we have
    # (follow-up call could request more, but for now keep it simple)
    return normalized[:10]  # Cap at 10


def compute_frames_and_hms(items: List[Dict[str, Any]], fps: float) -> List[Dict[str, Any]]:
    """Add frame numbers and HH:MM:SS timestamps to each highlight."""
    result = []
    for idx, item in enumerate(items, 1):
        start_s = item["start_seconds"]
        end_s = item["end_seconds"]
        
        start_frame = round(start_s * fps)
        end_frame = round(end_s * fps)
        
        start_hms = _format_hms(start_s)
        end_hms = _format_hms(end_s)
        
        result.append({
            "index": idx,
            "label": item["label"],
            "start_seconds": start_s,
            "end_seconds": end_s,
            "start_hms": start_hms,
            "end_hms": end_hms,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "why_high_converting": item["why_high_converting"],
            "emotional_hook": item["emotional_hook"],
            "suggested_caption": item["suggested_caption"]
        })
    
    return result


def write_output(video_meta: Dict[str, Any], highlights: List[Dict[str, Any]], output_path: Path):
    """Write final JSON output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    payload = {
        "video": video_meta,
        "highlights": highlights
    }
    
    with open(output_path, 'w') as f:
        json.dump(payload, f, indent=2)


def select_highlights(video_path: str, api_key: str = None, output_root: Path = None,
                     file_id: str = None, model_name: str = "models/gemini-2.5-pro"):
    """Main workflow for selecting highlights."""
    
    # Configure API
    if api_key:
        genai.configure(api_key=api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY environment variable")
        sys.exit(1)
    
    printer = ProgressPrinter()
    
    # Probe video
    print("Probing video metadata...", file=sys.stderr)
    fps, duration_seconds = probe_video_metadata(video_path)
    print(f"Video: {duration_seconds:.1f}s @ {fps:.2f} FPS", file=sys.stderr)
    
    # Upload or reuse
    video_file, own_upload, upload_elapsed, total_bytes = upload_or_get_file(video_path, file_id, printer)
    
    # Process with ETA
    printer.println("Processing video...")
    est_total = initial_processing_estimate(total_bytes, upload_duration_s=upload_elapsed)
    start_time = time.monotonic()
    
    try:
        while video_file.state.name == "PROCESSING":
            elapsed = time.monotonic() - start_time
            if elapsed >= est_total * 0.9:
                est_total = max(est_total, elapsed * 1.25)
            remaining = max(0.0, est_total - elapsed)
            printer.update_line(f"Processing... (elapsed: {human_duration(elapsed)}, est. {human_duration(remaining)} remaining)")
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
    
    # Load marketing guide
    print("Loading wrestling marketing guide...", file=sys.stderr)
    guide = load_marketing_guide()
    
    # Build and send prompt
    print("Generating highlights with Gemini 2.5 Pro...", file=sys.stderr)
    prompt = build_prompt(guide, duration_seconds, fps, Path(video_path).stem)
    
    model = genai.GenerativeModel(model_name)
    
    try:
        response = _generate_with_retry(
            model,
            [video_file, prompt],
            generation_config={"temperature": 0.2, "response_mime_type": "application/json"}
        )
        
        # Parse response
        items = parse_and_validate(response.text, duration_seconds)
        print(f"Parsed {len(items)} highlight candidates", file=sys.stderr)
        
        # Normalize
        normalized = normalize_highlights(items, duration_seconds)
        print(f"Normalized to {len(normalized)} non-overlapping segments", file=sys.stderr)
        
        # Compute frames and HH:MM:SS
        final_highlights = compute_frames_and_hms(normalized, fps)
        
        # Output
        paths = get_output_paths(video_path, output_root)
        highlights_json = paths["root"] / "highlights" / f"{Path(video_path).stem}_highlights.json"
        highlights_json.parent.mkdir(parents=True, exist_ok=True)
        
        video_meta = {
            "stem": Path(video_path).stem,
            "source_path": str(Path(video_path).absolute()),
            "duration_seconds": duration_seconds,
            "fps": fps
        }
        
        write_output(video_meta, final_highlights, highlights_json)
        
        print("\n" + "="*80)
        print("HIGHLIGHTS EXTRACTED SUCCESSFULLY")
        print("="*80)
        print(f"Output: {highlights_json}")
        print(f"Total highlights: {len(final_highlights)}")
        for h in final_highlights:
            print(f"  [{h['index']}] {h['label'].upper()} | {h['start_hms']}→{h['end_hms']} ({h['start_frame']}→{h['end_frame']} frames) | {h['emotional_hook']}")
        print("="*80)
        
    except Exception as e:
        print(f"Error generating highlights: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Extract 10 promo-ready wrestling highlight moments with frame and timestamp outputs"
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
    
    select_highlights(
        args.video,
        api_key=args.api_key,
        output_root=Path(args.output_root) if args.output_root else None,
        file_id=args.file_id,
        model_name=args.model
    )


if __name__ == "__main__":
    main()
