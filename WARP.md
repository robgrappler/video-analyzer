# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This repository provides two analysis tools:
- Gemini Analyzer (gemini_analyzer.py): full-video analysis via Google Gemini 2.5 Pro with optional wrestling-specific sales metrics.
- Gemini Thumbnails (gemini_thumbnails.py): identifies high-CTR moments and extracts frames, with wrestling-focused targeting.

## Architecture (big picture)

- Gemini Analyzer
  - Configures API key (env var or --api-key), uploads the raw video to Google Generative AI, and polls until processing completes.
  - Uses model "models/gemini-2.5-pro" to generate analysis in multiple modes: generic (legacy 6 categories), wrestling (sales-focused metrics), or both (default).
  - Extracts structured JSON data for programmatic use (includes intensity ratings, technical assessments, sales copy kit).
  - Saves text output to {video_stem}_gemini_analysis.txt and optional JSON to {video_stem}_analysis.json.
- Gemini Thumbnails
  - Uploads video to Gemini, requests selection of 8–12 wrestling-focused high-CTR moments via JSON.
  - Targets pin attempts, takedowns, scrambles, submission threats, victory poses for grappling audience conversion.
  - Deduplicates results (collapses timestamps <3s apart) and extracts frames using ffmpeg.
  - Saves frames to {video_stem}_thumbnails/ directory with wrestling labels/crop hints in {video_stem}_thumbnails.json.

## Commands (dev/run)

Prereqs
```bash
# Python deps
pip install google-generativeai

# Make scripts runnable (one-time)
chmod +x gemini_analyzer.py gemini_thumbnails.py

# Ensure ffmpeg is available on PATH (for thumbnail extraction)
which ffmpeg
```

Run: Full Video Analysis
```bash
# Provide API key via env var (replace with your secret)
export GEMINI_API_KEY={{GEMINI_API_KEY}}

# Wrestling-focused analysis (default mode)
./gemini_analyzer.py video.mp4
./gemini_analyzer.py video.mp4 --mode both --json-out analysis.json

# Legacy mode only
./gemini_analyzer.py video.mp4 --mode generic

# Wrestling sales metrics only
./gemini_analyzer.py video.mp4 --mode wrestling --cta-url "https://example.com/buy"

# With explicit MIME type override
./gemini_analyzer.py video.mp4 --mime-type "video/mp4"
```

Progress Tracking (to stderr):
- **Upload progress**: `Uploading: 12.5 MB / 150 MB (8.3 MB/s)` updates in real-time
- **Processing ETA**: `Processing... (elapsed: 45s, est. 2m remaining)` updates during Gemini analysis
- Heuristic ETA uses file size and upload duration to estimate processing time
- If actual processing exceeds 90% of estimate, ETA adapts upward to avoid misleading remaining time
- Final lines: `Upload complete in X at Y avg` and `Processing complete in Z`

Run: Wrestling-Focused Thumbnail Extraction
```bash
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_thumbnails.py video.mp4

# Complete workflow example
./gemini_analyzer.py "/Users/ppt04/Movies/New Folder With Items/Nocturmex-Match3.mp4" --mode both --json-out Nocturmex-Match3_analysis.json
./gemini_thumbnails.py "/Users/ppt04/Movies/New Folder With Items/Nocturmex-Match3.mp4"
```

Notes
- The local LLaVA-based analyzer has been removed.

## Key file entry points
- gemini_analyzer.py: main() sets up API key and calls analyze_video_gemini using "models/gemini-2.5-pro".
- gemini_thumbnails.py: main() sets up API key and calls select_and_extract_thumbnails, which requests JSON via _generate_with_retry, extracts frames, and manages metadata.

## Output conventions
- Gemini Analysis: {name}_gemini_analysis.txt labeled "GEMINI 2.5 PRO VIDEO ANALYSIS (with WRESTLING SALES REPORT)" for wrestling modes.
- JSON extraction: {name}_analysis.json with structured data (intensity_10, technical_rating_10, sales copy kit, etc.)
- Thumbnails: {name}_thumbnails/ directory with wrestling-labeled frames, {name}_thumbnails.json with crop hints and CTR hooks.
- Combined output: Analysis file includes "THUMBNAIL PICKS (WRESTLING)" section when both tools are used.

## Wrestling Analysis Categories
See docs/WRESTLING_MARKETING_GUIDE.md for detailed target audience insights and copywriting guidelines.
