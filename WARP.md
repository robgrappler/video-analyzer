# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This repository provides three video analysis tools:
- Gemini Analyzer (gemini_analyzer.py): full-video analysis via Google Gemini 2.5 Pro with optional wrestling-specific sales metrics.
- Gemini Thumbnails (gemini_thumbnails.py): identifies high-CTR moments and extracts frames, with wrestling-focused targeting.
- Gemini Editing Guide (gemini_editing_guide.py): generates timecoded video editing recommendations optimized for wrestling buyer conversion.
- Resolve Lua Apply Edits (scripts/resolve_lua_apply_edits.lua): DaVinci Resolve automation script to apply editing guide as markers.

## Architecture (big picture)

- Gemini Analyzer
  - Configures API key (env var or --api-key), uploads the raw video to Google Generative AI, and polls until processing completes.
  - Uses model "models/gemini-2.5-pro" to generate a structured, multi-section analysis from the full video without manual frame extraction.
  - Saves output to {video_stem}_gemini_analysis.txt and deletes the uploaded file from Gemini.
- Gemini Thumbnails
  - Uploads video to Gemini, requests selection of 5–10 distinct high-CTR moments via JSON.
  - Deduplicates results (collapses timestamps <3s apart) and extracts frames using ffmpeg.
  - Saves frames to {video_stem}_thumbnails/ directory, metadata to {video_stem}_thumbnails.json, and appends to {video_stem}_gemini_analysis.txt.
- Gemini Editing Guide
  - Analyzes video with Gemini 2.5 Pro to identify high-impact editing opportunities (slow-mo, zoom, SFX, color grading).
  - Grounds recommendations in docs/WRESTLING_MARKETING_GUIDE.md psychology (dominance, drama, intensity, technical appeal).
  - Optional: accepts existing analysis JSON (--analysis-json) to anchor edits to known key moments.
  - Outputs human-readable guide {video_stem}_editing_guide.txt with quickstart instructions and timecoded edits.
  - Outputs DaVinci Resolve-friendly JSON {video_stem}_editing_guide.json with structured parameters (informational in v1, automation-ready structure).
- Resolve Apply Edits (Lua)
  - Runs within DaVinci Resolve via Fusion script interpreter on macOS (fuscript -l lua).
  - Reads editing guide JSON, parses timecodes, and maps edit techniques to Resolve timeline markers (color-coded by intensity 1–5).
  - Creates/loads projects and timelines at 30fps; imports source media if path is valid.
  - Generates comprehensive JSON run log documenting marker placement, API availability, and TODOs for manual follow-up (visual effects, audio ops).
  - Gracefully degrades when Resolve API unavailable (dry-run mode); always generates run log for review.

## Commands (dev/run)

Prereqs
```bash
# Python deps
pip install google-generativeai

# Make scripts runnable (one-time)
chmod +x gemini_analyzer.py gemini_thumbnails.py gemini_editing_guide.py

# Ensure ffmpeg is available on PATH (for thumbnail extraction and duration check)
which ffmpeg
```

Run: Full Video Analysis
```bash
# Provide API key via env var (replace with your secret)
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_analyzer.py video.mp4

# Or pass explicitly (not recommended to store in shell history)
./gemini_analyzer.py video.mp4 --api-key {{GEMINI_API_KEY}}
```

Progress Tracking (to stderr):
- **Upload progress**: `Upload complete in X at Y avg` summary after upload (completion stats)
- **Processing ETA**: `Processing... (elapsed: 45s, est. 2m remaining)` updates during Gemini analysis
- Heuristic ETA uses file size and upload duration to estimate processing time
- If actual processing exceeds 90% of estimate, ETA adapts upward to avoid misleading remaining time
- Final lines: `Upload complete in X at Y avg` and `Processing complete in Z`

This behavior now applies to Analyzer, Thumbnails, and Editing Guide.

Run: Thumbnail Extraction
```bash
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_thumbnails.py video.mp4
```

Run: Editing Guide Generation
```bash
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_editing_guide.py video.mp4

# With prior analysis for context
./gemini_editing_guide.py video.mp4 --analysis-json video_analysis.json

# Control output size and determinism
./gemini_editing_guide.py video.mp4 --max-edits 20 --temperature 0.2
```

Run: Apply Editing Guide to DaVinci Resolve (Lua, via Fusion script interpreter)
```bash
# Via environment variable
export EDITING_GUIDE_JSON={{PATH_TO_EDITING_GUIDE_JSON}}
"/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fuscript" \
  -l lua scripts/resolve_lua_apply_edits.lua [--project-name "My Project"] [--dry-run]

# Or via --json argument
"/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fuscript" \
  -l lua scripts/resolve_lua_apply_edits.lua --json {{PATH_TO_EDITING_GUIDE_JSON}} \
  [--project-name "My Project"] [--color-preset MyColor] [--vignette-preset MyVignette] [--dry-run]

# Check the run log (always generated)
cat {{GUIDE_DIR}}/{{stem}}_resolve_apply_log.json
```

Run: Apply Editing Guide to DaVinci Resolve (Python, external CLI)
```bash
# From repo root (auto-discovers DaVinciResolveScript on macOS; no PYTHONPATH needed)
python3 scripts/resolve_studio_apply_edits.py --json /path/to/editing_guide.json \
    [--project-name "My Project"] [--dry-run]

# From any directory (absolute script path)
python3 /Users/ppt04/Github/video-analyzer/scripts/resolve_studio_apply_edits.py \
    --json /path/to/editing_guide.json [--project-name "My Project"] [--dry-run]

# Custom Resolve installation path (env var override)
export RESOLVE_SCRIPT_API="/path/to/DaVinci Resolve/Developer/Scripting/Modules"
python3 scripts/resolve_studio_apply_edits.py --json /path/to/editing_guide.json
```

Python API auto-discovery:
- Auto-discovers DaVinciResolveScript module at macOS default path: `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/`
- No PYTHONPATH configuration required
- Supports env var override via `RESOLVE_SCRIPT_API` for custom installs
- Requires Resolve running and external scripting enabled: `Preferences > System > General > External scripting using`
- Gracefully falls back to dry-run mode if API unavailable
- For in-Resolve console execution, use `scripts/resolve_studio_apply_edits_console.py` instead

Resolve API behavior (macOS):
- **Dry-run mode** (default when API unavailable): Computes markers and logs but does not mutate Resolve.
- **Live mode** (requires Resolve open + scripting enabled): Attempts to create project, timeline, and markers.
- Both modes generate a run log with timestamp, edit details, TODOs, and API capability info.
- Visual effects and audio operations are logged as TODOs; only markers are created in v1.
- Lua version: primary in-Resolve pathway via Fusion script interpreter
- Python version: external CLI for automation workflows

Notes
- The local LLaVA-based analyzer has been removed.
- Lua script entry: scripts/resolve_lua_apply_edits.lua (pure-Lua implementation for macOS Fusion compatibility; replaced Python version).

## Key file entry points
- gemini_analyzer.py: main() sets up API key and calls analyze_video_gemini using "models/gemini-2.5-pro".
- gemini_thumbnails.py: main() sets up API key and calls select_and_extract_thumbnails, which requests JSON via _generate_with_retry, extracts frames, and manages metadata.
- gemini_editing_guide.py: main() loads marketing guide, builds prompt with JSON schema, uploads video, calls Gemini for editing recommendations, validates/normalizes JSON output, and generates both human-readable .txt and Resolve-friendly .json files.
- scripts/resolve_lua_apply_edits.lua: main() parses CLI args, reads editing guide JSON (with embedded pure-Lua parser), detects Resolve API availability, normalizes edits, creates/loads project, builds markers, and writes run log.

## Output conventions
- Per-video folder under project root: ./{name}/
  - analysis/{name}_gemini_analysis.txt labeled "GEMINI 2.5 PRO VIDEO ANALYSIS" (+ optional analysis/{name}_analysis.json)
  - thumbnails/ extracted frames and thumbnails/{name}_thumbnails.json; thumbnails section appended to analysis/{name}_gemini_analysis.txt
  - editing_guide/{name}_editing_guide.txt and editing_guide/{name}_editing_guide.json
