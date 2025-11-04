#!/usr/bin/env python3
"""
Wrestling Sales Report using Google Gemini 2.5 Pro
Generates a conversion-focused wrestling report and JSON metrics.
"""

import os
import sys
import argparse
import time
import random
from pathlib import Path
import mimetypes
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


def build_wrestling_report_prompt(cta_url: str = None) -> str:
    return f"""You are a specialist analyst of amateur grappling and wrestling videos.

PART B — WRESTLING SALES REPORT (Detailed, conversion-focused)

1) MATCH INTENSITY & COMPETITIVENESS LEVEL
   - Rate intensity_10 (1=relaxed drill, 10=all-out war)
   - Rate competitiveness_10 (1=runaway, 10=razor-thin)
   - List momentum_shifts: each entry is {{start_s, end_s, who_led (A|B|even), why}}
   - Balance descriptor: back-and-forth | chess-match | grinder | runaway | mixed

2) TECHNICAL SKILLS DEMONSTRATION
   - Document each technique with {{name, type (takedown/control/transition/pin/escape/submission), difficulty_5, cleanliness (crisp|gritty), effectiveness (high|mid|low), start_s, end_s}}
   - Overall technical_rating_10 (1=sloppy, 10=pristine)
   - Wrestling style: folkstyle | freestyle | submission grappling | mixed | pro-style elements

3) PHYSICAL ATTRIBUTES & CHEMISTRY
   - Physiques: For each participant, describe {{descriptor (lean|muscular|stocky|athletic), definition_5, conditioning_5, gear_notes}}
   - Chemistry: competitive tension | friendly rivalry | alpha-vs-alpha | playful roughhousing
   - heat_factor_5 (1=cold/clinical, 5=intense/charged) — describe sweat/sheen, close contact intensity, lingering holds (non-explicit)

4) HIGHLIGHT MOMENTS (Purchase Drivers)
   - List 8–12 moments: {{time_s, type (comeback|dominance|technical_exchange|intense_scramble|near_fall|submission_threat), why_it_hooks, suggested_thumbnail_time_s}}

5) ENTERTAINMENT VALUE
   - rewatch_value_10 (would fans watch this again?)
   - Segments who will love this: technique_nerds | domination_fans | stamina_fans | balanced_fans

6) MATCH STRUCTURE & PACING
   - Narrative arc: opening → mid-match → finish (1–2 sentences each)
   - pacing_curve: {{early_10, mid_10, late_10}} — how fast/slow each segment feels

7) PRODUCTION QUALITY & PRESENTATION
   - capture_rating_10 (1=unwatchable, 10=broadcast-quality)
   - Camera, lighting, audio observations (mat slaps, breathing, grunts)
   - 2–3 quick improvements

8) SALES COPY KIT (Conversion-focused)
   - titles: 3 punchy titles (≤70 chars each)
   - descriptions: 2 compelling 2-sentence descriptions (store-ready)
   - bullets: 5 selling points emphasizing intensity, skill, chemistry, physique appeal (safe, non-explicit)
   - cta: "Watch the full match to see [dramatic hook]." {f'({cta_url})' if cta_url else '(no URL)'}
   - buyer_tags: 5–8 tags like "back-and-forth", "technical", "alpha-energy", "dominant-display", "lean-vs-muscular", etc.

IMPORTANT GUARDRAILS:
- Avoid explicit sexual description; describe heat and intensity without graphic details
- Do not invent identities; use only visible/audible information
- Use seconds for all timestamps
- Language should be persuasive, honest, and tailored to gay male amateur grappling fans (ages 20–60)

At the end, output [BEGIN JSON] followed by a JSON object with these keys:
{
  "intensity_10": int,
  "competitiveness_10": int,
  "momentum_shifts": [{"start_s": int, "end_s": int, "who_led": "A|B|even", "why": "string"}],
  "technical_rating_10": int,
  "techniques": [{"name": "string", "type": "takedown|control|transition|pin|escape|submission", "difficulty_5": int, "cleanliness": "crisp|gritty", "effectiveness": "high|mid|low", "start_s": int, "end_s": int}],
  "style": "folkstyle|freestyle|submission grappling|mixed|pro-style elements",
  "physiques": [{"descriptor": "lean|muscular|stocky|athletic", "definition_5": int, "conditioning_5": int, "gear_notes": "string"}],
  "heat_factor_5": int,
  "highlight_moments": [{"time_s": int, "type": "comeback|dominance|technical_exchange|intense_scramble|near_fall|submission_threat", "why_it_hooks": "string", "suggested_thumbnail_time_s": int}],
  "rewatch_value_10": int,
  "pacing_curve": {"early_10": int, "mid_10": int, "late_10": int},
  "capture_rating_10": int,
  "titles": ["string"],
  "descriptions": ["string"],
  "bullets": ["string"],
  "cta": "string",
  "buyer_tags": ["string"]
}
[END JSON]
"""


def main():
    parser = argparse.ArgumentParser(description="Generate wrestling sales report (with JSON) using Gemini 2.5 Pro")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--api-key", help="Google Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--mime-type", help="Override MIME type (e.g., 'video/mp4')")
    parser.add_argument("--max-output-tokens", type=int, default=8192, help="Cap for model output length")
    parser.add_argument("--cta-url", help="Optional URL to include in Sales Copy CTA")
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

    # Detect MIME type
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

    # Generate report
    model = genai.GenerativeModel("models/gemini-2.5-pro")
    prompt = build_wrestling_report_prompt(args.cta_url)
    gen_config = {"max_output_tokens": int(args.max_output_tokens)} if args.max_output_tokens else None

    try:
        response = _generate_with_retry(model, [video_file, prompt], generation_config=gen_config)
    except Exception as e:
        print(f"Error generating report: {e}")
        sys.exit(1)
    finally:
        try:
            genai.delete_file(video_file.name)
            print("Cleaned up uploaded video from Gemini")
        except Exception:
            pass

    # Write outputs
    paths = get_output_paths(args.video, Path(args.output_root) if args.output_root else None)
    stem = Path(args.video).stem
    txt_path = paths["analysis_dir"] / f"{stem}_sales_report.txt"
    json_path = paths["analysis_json"]

    with open(txt_path, 'w') as f:
        f.write("GEMINI 2.5 PRO — WRESTLING SALES REPORT\n")
        f.write("=" * 60 + "\n\n")
        f.write(response.text)

    # Extract and save JSON block if present
    text = response.text
    if "[BEGIN JSON]" in text and "[END JSON]" in text:
        js = text[text.find("[BEGIN JSON]") + len("[BEGIN JSON]"): text.find("[END JSON]")].strip()
        import json
        try:
            data = json.loads(js)
            with open(json_path, 'w') as jf:
                json.dump(data, jf, indent=2)
            print(f"Analysis JSON saved to: {json_path}")
        except Exception as e:
            print(f"Warning: Could not parse JSON block: {e}")

    print(f"\nSales report saved to: {txt_path}")


if __name__ == "__main__":
    main()