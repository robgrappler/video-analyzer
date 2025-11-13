# gemini_highlights.py

Wrestling promo highlight selector using Google Gemini 2.5 Pro.

Identifies exactly **10 high-converting highlight moments** (~5 seconds each) optimized for wrestling buyer conversion, with output in multiple timestamp formats (seconds, frames, HH:MM:SS).

## Overview

This tool:
- Uploads a wrestling video to Google Gemini 2.5 Pro
- Analyzes it using your wrestling marketing psychology guide
- Returns 10 non-overlapping highlight segments (~5s each) tailored for promo intros
- Computes frame numbers using actual source video FPS
- Outputs structured JSON with emotional hooks and conversion reasoning

**No media extraction:** Just metadata and timestamps (no thumbnail extraction, no MP4 clips).

## Installation

Ensure dependencies are installed:

```bash
pip install google-generativeai
```

Verify `ffmpeg` and `ffprobe` are available:

```bash
which ffprobe ffmpeg
```

## Usage

### Basic: Upload and analyze

```bash
export GEMINI_API_KEY=your_key_here
./gemini_highlights.py /path/to/video.mp4
```

### Explicit API key

```bash
./gemini_highlights.py /path/to/video.mp4 --api-key your_key_here
```

### Reuse an existing upload (faster re-analysis)

```bash
./gemini_highlights.py /path/to/video.mp4 --file-id files/abc123xyz
```

### Custom output directory

```bash
./gemini_highlights.py /path/to/video.mp4 --output-root /custom/output/path
```

### Use a different model

```bash
./gemini_highlights.py /path/to/video.mp4 --model models/gemini-1.5-pro
```

## Output

### File structure

```
<video_stem>/
  highlights/
    <video_stem>_highlights.json    ← Main output
```

### JSON schema

```json
{
  "video": {
    "stem": "match_2025",
    "source_path": "/full/path/to/video.mp4",
    "duration_seconds": 840.5,
    "fps": 29.97
  },
  "highlights": [
    {
      "index": 1,
      "label": "dominance",
      "start_seconds": 120.5,
      "end_seconds": 125.3,
      "start_hms": "00:02:00",
      "end_hms": "00:02:05",
      "start_frame": 3609,
      "end_frame": 3753,
      "why_high_converting": "Displays dominant control and physical conditioning appeal",
      "emotional_hook": "Watch him establish complete control",
      "suggested_caption": "Total dominance on display"
    },
    ...9 more...
  ]
}
```

### Understanding the output

- **index**: Position in promo (1–10)
- **label**: Moment type: `dominance`, `technical_exchange`, `comeback`, `submission_threat`, `near_fall`, `scramble`, `victory`, `control`, or `takedown`
- **start_seconds / end_seconds**: Timestamp in decimal seconds
- **start_hms / end_hms**: Formatted HH:MM:SS
- **start_frame / end_frame**: Frame numbers computed using actual video FPS
- **why_high_converting**: Marketing rationale grounded in wrestling psychology
- **emotional_hook**: Buyer-facing hook (suitable for thumbnails/captions)
- **suggested_caption**: ≤8-word promotional caption

## Moment types prioritized

The tool looks for these conversion-driving wrestling moments:

1. **Pin attempts & near-falls** – Dramatic tension, close finishes
2. **Takedowns with impact** – Power display, control establishment
3. **Submission threats** – Suspense, technical mastery, fear factor
4. **Dominant control positions** – Alpha energy, physical conditioning
5. **Victory poses** – Payoff satisfaction, confidence display
6. **Momentum shifts & comebacks** – Narrative arc, underdog appeal
7. **Technical exchanges** – Wrestling skill, complexity, chess-match feel
8. **Intense scrambles** – Athleticism, excitement, close-contact action

## How it works

1. **Probe video** – Detects actual FPS and duration via `ffprobe`
2. **Upload** – Sends to Gemini 2.5 Pro (or reuses `--file-id`)
3. **Processing** – Waits with ETA updates
4. **Prompting** – Grounds Gemini in your marketing guide; requests exactly 10 non-overlapping ~5s segments
5. **Validation** – Enforces constraints: 5s duration, 2s spacing, label validation
6. **Frame math** – Computes frame numbers using actual video FPS
7. **Output** – Writes JSON and prints summary

## Progress & feedback

The tool provides realtime progress:

```
Probing video metadata...
Video: 840.5s @ 29.97 FPS
Uploading video: /path/to/video.mp4
Uploading... (elapsed: 45s)
Upload complete in 52s at 3.2 MB/s avg
Uploaded: files/abc123xyz
Processing video...
Processing... (elapsed: 23s, est. 18s remaining)
Processing complete in 42s
Loading wrestling marketing guide...
Generating highlights with Gemini 2.5 Pro...
Parsed 12 highlight candidates
Normalized to 10 non-overlapping segments

================================================================================
HIGHLIGHTS EXTRACTED SUCCESSFULLY
================================================================================
Output: ./match_2025/highlights/match_2025_highlights.json
Total highlights: 10
  [1] DOMINANCE | 00:02:00→00:02:05 (3609→3753 frames) | Watch him establish complete control
  [2] TAKEDOWN | 00:05:15→00:05:20 (9406→9550 frames) | Explosive power display
  ... (8 more)
================================================================================
```

## Marketing guide grounding

The script loads `docs/WRESTLING_MARKETING_GUIDE.md` to ground highlight selection in:
- **Intensity & Drama** – Tension, near-falls, momentum
- **Dominance & Power** – Control, submission threats, poses
- **Technical Mastery** – Clean holds, difficult escapes, IQ
- **Physical Appeal** – Conditioning, sweat, close contact
- **Narrative Arc** – Opening impact, swings, finish
- **Buyer Hooks** – Competitiveness, chemistry, rewatch value

Ensures highlights are chosen for buyer conversion, not just entertainment.

## Error handling

- **Missing API key**: Clear message; suggests env var or `--api-key`
- **ffprobe not found**: Actionable error; reminds to install ffmpeg
- **Invalid video**: Early exit with clear error message
- **Model returns non-JSON**: Attempts to extract JSON block; surfaces final error
- **Fewer than 10 highlights**: Returns what model found (you can re-run with `--file-id`)
- **Overlapping segments**: Automatically resolves by nudging later segments or dropping duplicates

## Advanced: Reuse file uploads

For rapid iteration during development, save the Gemini file ID after first run:

```bash
# First run (full upload & processing)
./gemini_highlights.py video.mp4 2>&1 | tee run1.log

# Extract file ID from Gemini response (appears in upload summary)
# e.g., "Uploaded: files/abc123xyz"

# Reuse same upload for second run (skips upload & processing)
./gemini_highlights.py video.mp4 --file-id files/abc123xyz
# Much faster; goes straight to highlight generation
```

## File retention

**Important:** Uploaded files are **NOT deleted** by this script. Use a separate command to clean up:

```bash
# Delete file from Gemini (if needed)
# You'll need to use another tool or Gemini API directly
```

The file ID is useful for re-analysis without re-uploading large videos.

## Tips for best results

1. **Quality source video** – Ensure clear, well-lit wrestling footage
2. **Authentic wrestling moments** – Real matches convert better than drills
3. **Multiple re-runs** – If output feels off, try again (Gemini may pick different moments each run due to temperature=0.2; you control variability)
4. **Review captions** – Suggested captions are generated; consider refining for your brand voice
5. **Frame accuracy** – Frame numbers are computed from actual FPS; use for precise editing timelines

## CLI reference

```
usage: gemini_highlights.py [-h] [--api-key API_KEY] [--output-root OUTPUT_ROOT] 
                            [--model MODEL] [--file-id FILE_ID]
                            video

Extract 10 promo-ready wrestling highlight moments with frame and timestamp outputs

positional arguments:
  video                 Path to video file

options:
  -h, --help            show this help message and exit
  --api-key API_KEY     Google Gemini API key (or set GEMINI_API_KEY env var)
  --output-root OUTPUT_ROOT
                        Optional root directory for outputs (default: current working directory)
  --model MODEL         Model name to use (e.g., 'models/gemini-1.5-pro')
  --file-id FILE_ID     Reuse an already uploaded Gemini file id (e.g., 'files/abc123'); skips local upload
```
