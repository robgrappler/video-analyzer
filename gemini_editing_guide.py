#!/usr/bin/env python3
"""
Video Editing Guide Generator using Google Gemini 2.5 Pro
Generates timecoded editing recommendations for wrestling match videos
"""

import os
import sys
import argparse
import json
import time
import random
import subprocess
from pathlib import Path
from datetime import datetime
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded


def _human_time(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    s = int(max(0, round(float(seconds))))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_hhmmss(hhmmss: str) -> float:
    """Parse HH:MM:SS to seconds."""
    parts = hhmmss.strip().split(":")
    try:
        if len(parts) == 3:
            h, m, s = [int(p) for p in parts]
            return float(h * 3600 + m * 60 + s)
        elif len(parts) == 2:
            m, s = [int(p) for p in parts]
            return float(m * 60 + s)
        else:
            return float(parts[0])
    except (ValueError, IndexError):
        return 0.0


def _parse_retry_delay(exc: Exception) -> float:
    """Try to parse server-suggested retry delay (seconds) from exception text."""
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


def _generate_with_retry(model, parts, generation_config=None, max_retries: int = 3, initial_delay: float = 5.0, backoff: float = 2.0):
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


def load_marketing_guide() -> str:
    """Load wrestling marketing guide or return fallback summary."""
    guide_path = Path(__file__).parent / "docs" / "WRESTLING_MARKETING_GUIDE.md"
    try:
        with open(guide_path, 'r') as f:
            content = f.read()
            # Extract key sections for prompt (trim if too large)
            if len(content) > 8000:
                # Extract key psychological hooks and editing principles
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
        # Fallback summary if guide missing
        return """Wrestling Marketing Psychology (Summary):
- Intensity & Drama: Emphasize tension, near-falls, momentum shifts
- Dominance & Power: Highlight control positions, submission threats, victory poses
- Technical Mastery: Showcase clean technique, difficult holds, wrestling IQ
- Physical Appeal: Athletic conditioning, sweat/sheen, close contact
- Narrative Arc: Opening impact, mid-match swings, decisive finish
- Buyer Hooks: Competitiveness, chemistry, rewatchability"""


def build_prompt(marketing_guide: str, duration_hhmmss: str, max_edits: int, analysis_json: dict = None) -> str:
    """Build the Gemini prompt with JSON schema and marketing psychology."""
    
    analysis_context = ""
    if analysis_json:
        analysis_context = f"""\n\nPRIOR ANALYSIS CONTEXT (use to anchor edits to key moments):
{json.dumps(analysis_json, indent=2)[:2000]}\n...
"""
    
    prompt = f"""You are a wrestling sales-focused video editor coach. Your task is to generate a comprehensive video editing guide for a wrestling/grappling match that maximizes buyer conversion.

VIDEO DURATION: {duration_hhmmss}

MARKETING PSYCHOLOGY FOUNDATION:
{marketing_guide}

{analysis_context}

Your goal: Identify {max_edits} or fewer high-impact editing opportunities that emphasize:
- Pin attempts & near-falls (dramatic tension)
- Takedowns & impacts (power display)
- Submission threats (suspense building)
- Dominant control positions (alpha energy)
- Victory moments (payoff satisfaction)
- Momentum shifts & comebacks (narrative arc)

For each editing recommendation, specify:
1. Precise timecode range (HH:MM:SS format)
2. Editing techniques to apply (slow_motion, zoom, sfx, color_grade, speed_ramp, etc.)
3. Parameters for each technique
4. Why this edit appeals to wrestling buyers (reference marketing psychology)
5. Simple DaVinci Resolve implementation hints

Return ONLY valid JSON with this exact schema:

{{
  "guide_version": "1.0.0",
  "video": {{
    "duration_hhmmss": "{duration_hhmmss}",
    "analysis_timestamp": "{datetime.now().isoformat()}"
  }},
  "edits": [
    {{
      "id": "E001",
      "label": "Brief descriptive label",
      "start": "HH:MM:SS",
      "end": "HH:MM:SS",
      "intensity_1_5": 1-5,
      "edits": [
        {{
          "type": "slow_motion|zoom|sfx|color_grade|speed_ramp|vignette|crop_reframe|audio_ducking",
          "parameters": {{"factor": 0.5, "ramp": "ease_in_out"}}
        }}
      ],
      "why_this_works": "Explanation referencing marketing psychology (dominance/drama/impact/tension)",
      "resolve_hint": {{
        "video_track": "V1",
        "audio_track": "A1",
        "effects_map": [
          "Retime Curve: constant 50%",
          "Transform: keyframe Zoom 1.0→1.2"
        ]
      }}
    }}
  ],
  "notes": {{
    "marketing_refs": [
      "Key marketing principles emphasized"
    ],
    "promo_cut_hint": "Future: 30-60s max-drama montage (not implemented)"
  }}
}}

IMPORTANT:
- All timecodes MUST be within 00:00:00 to {duration_hhmmss}
- Return ONLY the JSON object, no additional text
- Edits should be sorted chronologically by start time
- Focus on conversion-driving moments per marketing guide
- Keep resolve_hint simple and actionable
"""
    return prompt


def parse_and_validate_json(raw_text: str, duration_seconds: float, max_edits: int) -> dict:
    """Extract, parse, and validate JSON from Gemini response."""
    # Strip code fences and extract JSON
    text = raw_text.strip()
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0]
    elif '```' in text:
        text = text.split('```')[1].split('```')[0]
    
    # Find first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end+1]
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parse failed: {e}", file=sys.stderr)
        return {"guide_version": "1.0.0", "video": {}, "edits": [], "notes": {}}
    
    if "edits" not in data:
        data["edits"] = []
    
    # Normalize and validate each edit
    valid_edits = []
    allowed_types = {"slow_motion", "zoom", "sfx", "color_grade", "speed_ramp", 
                     "vignette", "crop_reframe", "audio_ducking", "filter"}
    
    for i, edit in enumerate(data["edits"][:max_edits]):
        try:
            # Parse timecodes
            start_s = _parse_hhmmss(edit.get("start", "00:00:00"))
            end_s = _parse_hhmmss(edit.get("end", "00:00:00"))
            
            # If end missing, set to start + 2s
            if end_s <= start_s:
                end_s = start_s + 2.0
            
            # Clamp to duration
            start_s = max(0.0, min(start_s, duration_seconds))
            end_s = max(start_s, min(end_s, duration_seconds))
            
            # Skip if invalid range
            if start_s >= end_s or start_s >= duration_seconds:
                continue
            
            # Normalize intensity
            intensity = edit.get("intensity_1_5", 3)
            intensity = max(1, min(5, int(intensity)))
            
            # Filter technique types
            edit_list = edit.get("edits", [])
            filtered_edits = []
            for e in edit_list:
                if e.get("type") in allowed_types:
                    filtered_edits.append(e)
            
            # Ensure resolve_hint exists
            if "resolve_hint" not in edit:
                edit["resolve_hint"] = {
                    "video_track": "V1",
                    "audio_track": "A1",
                    "effects_map": []
                }
            
            # Build normalized edit
            normalized = {
                "id": edit.get("id", f"E{i+1:03d}"),
                "label": edit.get("label", "Edit"),
                "start": _human_time(start_s),
                "end": _human_time(end_s),
                "intensity_1_5": intensity,
                "edits": filtered_edits,
                "why_this_works": edit.get("why_this_works", ""),
                "resolve_hint": edit["resolve_hint"]
            }
            valid_edits.append(normalized)
            
        except Exception as e:
            print(f"Warning: Skipping invalid edit {i}: {e}", file=sys.stderr)
            continue
    
    # Sort by start time
    valid_edits.sort(key=lambda e: _parse_hhmmss(e["start"]))
    
    data["edits"] = valid_edits
    return data


def generate_text_guide(data: dict, video_stem: str, video_path: str) -> str:
    """Generate human-readable editing guide from JSON data."""
    lines = []
    lines.append("=" * 80)
    lines.append("VIDEO EDITING GUIDE (Wrestling Conversion Focus) — GEMINI 2.5 PRO")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Video: {video_stem}")
    lines.append(f"Source: {video_path}")
    lines.append(f"Duration: {data.get('video', {}).get('duration_hhmmss', 'N/A')}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Guide Version: {data.get('guide_version', '1.0.0')}")
    lines.append("")
    lines.append("=" * 80)
    lines.append("QUICKSTART FOR NEWBIES")
    lines.append("=" * 80)
    lines.append("")
    lines.append("How to apply these edits in DaVinci Resolve or Final Cut Pro:")
    lines.append("")
    lines.append("SLOW MOTION:")
    lines.append("  - Resolve: Right-click clip → Retime Controls → Speed → 50% (or 25%)")
    lines.append("  - FCP: Select clip → Retime menu → Slow → 50%")
    lines.append("")
    lines.append("ZOOM (Push-in):")
    lines.append("  - Resolve: Inspector → Transform → Zoom → Add keyframes (1.0 → 1.2)")
    lines.append("  - FCP: Select clip → Transform → Add keyframes to Scale")
    lines.append("")
    lines.append("SOUND EFFECTS (SFX):")
    lines.append("  - Layer SFX on separate audio track above natural sound")
    lines.append("  - Reduce natural sound by -3 to -6 dB during SFX (audio ducking)")
    lines.append("  - Common SFX: impact boom, whoosh, tension drone")
    lines.append("")
    lines.append("COLOR GRADING:")
    lines.append("  - Resolve: Color page → Apply LUT or adjust Contrast/Saturation")
    lines.append("  - FCP: Color Board → Increase contrast, warmth for dominance")
    lines.append("  - 'Punchy' = +10-20% contrast, slight saturation boost")
    lines.append("")
    lines.append("=" * 80)
    lines.append("TIMECODED EDITING RECOMMENDATIONS")
    lines.append("=" * 80)
    lines.append("")
    
    edits = data.get("edits", [])
    if not edits:
        lines.append("No editing recommendations generated.")
        lines.append("")
    else:
        for edit in edits:
            lines.append(f"[{edit['start']} → {edit['end']}] {edit['label']} (Intensity: {edit['intensity_1_5']}/5)")
            lines.append("-" * 80)
            lines.append("")
            
            # Techniques
            techniques = edit.get('edits', [])
            if techniques:
                lines.append("TECHNIQUES:")
                for tech in techniques:
                    tech_type = tech.get('type', 'unknown')
                    params = tech.get('parameters', {})
                    param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                    if param_str:
                        lines.append(f"  • {tech_type.replace('_', ' ').title()}: {param_str}")
                    else:
                        lines.append(f"  • {tech_type.replace('_', ' ').title()}")
                lines.append("")
            
            # Why this works
            why = edit.get('why_this_works', '')
            if why:
                lines.append("WHY THIS WORKS FOR BUYERS:")
                lines.append(f"  {why}")
                lines.append("")
            
            # Resolve hints
            resolve_hint = edit.get('resolve_hint', {})
            effects_map = resolve_hint.get('effects_map', [])
            if effects_map:
                lines.append("DAVINCI RESOLVE IMPLEMENTATION:")
                for effect in effects_map:
                    lines.append(f"  • {effect}")
                lines.append("")
            
            lines.append("")
    
    # Closing checklist
    lines.append("=" * 80)
    lines.append("FINAL CHECKLIST")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Before exporting your edited match:")
    lines.append("  ☐ Open with high-impact moment (first 5 seconds hook)")
    lines.append("  ☐ Maintain rhythm: alternate tension/impact throughout")
    lines.append("  ☐ Ensure clarity on decisive moments (pins, taps, victory poses)")
    lines.append("  ☐ Audio: balance natural sound, SFX, and music (if added)")
    lines.append("  ☐ Color: consistent grade emphasizing athletic appeal")
    lines.append("  ☐ Pacing: no dead air longer than 10-15 seconds")
    lines.append("")
    lines.append("Export Settings (Recommended):")
    lines.append("  - Format: H.264 or H.265 (HEVC)")
    lines.append("  - Resolution: 1920x1080 or 3840x2160 (4K if source supports)")
    lines.append("  - Bitrate: 10-20 Mbps (1080p) or 40-60 Mbps (4K)")
    lines.append("  - Frame Rate: Match source (typically 30 or 60 fps)")
    lines.append("")
    
    # Marketing notes
    notes = data.get('notes', {})
    marketing_refs = notes.get('marketing_refs', [])
    if marketing_refs:
        lines.append("=" * 80)
        lines.append("MARKETING PRINCIPLES EMPHASIZED")
        lines.append("=" * 80)
        lines.append("")
        for ref in marketing_refs:
            lines.append(f"  • {ref}")
        lines.append("")
    
    lines.append("=" * 80)
    lines.append("END OF GUIDE")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Warning: Could not determine video duration: {e}", file=sys.stderr)
        return 0.0


def main():
    parser = argparse.ArgumentParser(
        description="Generate video editing guide with Gemini 2.5 Pro (wrestling conversion focus)"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--api-key",
        help="Google Gemini API key (or set GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--analysis-json",
        help="Optional path to existing analysis JSON for context"
    )
    parser.add_argument(
        "--mime-type",
        help="Override MIME type detection (e.g., 'video/mp4')"
    )
    parser.add_argument(
        "--max-edits",
        type=int,
        default=24,
        help="Maximum number of editing recommendations (default: 24)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature for deterministic output (default: 0.3)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)
    
    print("Video Editing Guide Generator - Starting...")
    print(f"Video: {args.video}")
    
    # Configure API key
    if args.api_key:
        genai.configure(api_key=args.api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY environment variable")
        sys.exit(1)
    
    # Get video duration
    print("Analyzing video metadata...", file=sys.stderr)
    duration_seconds = get_video_duration(args.video)
    if duration_seconds <= 0:
        print("Error: Could not determine video duration")
        sys.exit(1)
    duration_hhmmss = _human_time(duration_seconds)
    print(f"Video duration: {duration_hhmmss}", file=sys.stderr)
    
    # Load marketing guide
    print("Loading wrestling marketing guide...", file=sys.stderr)
    marketing_guide = load_marketing_guide()
    
    # Load optional analysis JSON
    analysis_data = None
    if args.analysis_json and Path(args.analysis_json).exists():
        try:
            with open(args.analysis_json, 'r') as f:
                analysis_data = json.load(f)
            print(f"Loaded analysis context from {args.analysis_json}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not load analysis JSON: {e}", file=sys.stderr)
    
    # Build prompt
    prompt = build_prompt(marketing_guide, duration_hhmmss, args.max_edits, analysis_data)
    
    # Detect MIME type
    import mimetypes
    mime_type = args.mime_type
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(args.video)
    if not mime_type:
        mime_type = "video/mp4"
    
    # Upload video
    print(f"Uploading video to Gemini...", file=sys.stderr)
    try:
        video_file = genai.upload_file(
            path=args.video,
            mime_type=mime_type,
            display_name=os.path.basename(args.video),
            resumable=True
        )
        print(f"Uploaded: {video_file.name}", file=sys.stderr)
    except Exception as e:
        print(f"Error uploading video: {e}")
        sys.exit(1)
    
    # Wait for processing
    print("Processing video...", file=sys.stderr)
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
    
    if video_file.state.name == "FAILED":
        print(f"Video processing failed: {video_file.state}")
        sys.exit(1)
    
    print("Video processed. Generating editing guide...", file=sys.stderr)
    
    # Generate editing guide
    try:
        model = genai.GenerativeModel("models/gemini-2.5-pro")
        
        generation_config = {
            "temperature": args.temperature,
            "response_mime_type": "application/json"
        }
        
        response = _generate_with_retry(
            model,
            [video_file, prompt],
            generation_config=generation_config
        )
        
        raw_response = response.text
        
    except Exception as e:
        print(f"Error generating guide: {e}")
        sys.exit(1)
    finally:
        # Cleanup uploaded file
        try:
            genai.delete_file(video_file.name)
            print("Cleaned up uploaded video from Gemini", file=sys.stderr)
        except Exception:
            pass
    
    # Parse and validate JSON
    print("Parsing and validating editing recommendations...", file=sys.stderr)
    data = parse_and_validate_json(raw_response, duration_seconds, args.max_edits)
    
    # Enrich video metadata
    if "video" not in data:
        data["video"] = {}
    data["video"]["stem"] = Path(args.video).stem
    data["video"]["source_path"] = str(Path(args.video).absolute())
    data["video"]["duration_hhmmss"] = duration_hhmmss
    data["video"]["mime_type"] = mime_type
    
    # Generate output files
    video_stem = Path(args.video).stem
    json_path = f"{video_stem}_editing_guide.json"
    txt_path = f"{video_stem}_editing_guide.txt"
    
    # Write JSON
    print(f"Writing JSON guide to {json_path}...", file=sys.stderr)
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Write text guide
    print(f"Writing text guide to {txt_path}...", file=sys.stderr)
    text_guide = generate_text_guide(data, video_stem, args.video)
    with open(txt_path, 'w') as f:
        f.write(text_guide)
    
    print("\n" + "=" * 80)
    print("EDITING GUIDE GENERATED SUCCESSFULLY")
    print("=" * 80)
    print(f"Text guide: {txt_path}")
    print(f"JSON data:  {json_path}")
    print(f"Total edits: {len(data.get('edits', []))}")
    print("=" * 80)


if __name__ == "__main__":
    main()
