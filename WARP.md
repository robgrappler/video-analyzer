# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This repository provides two analysis tools:
- Gemini Analyzer (gemini_analyzer.py): full-video analysis via Google Gemini 2.5 Pro.
- Gemini Thumbnails (gemini_thumbnails.py): identifies high-CTR moments and extracts frames.

## Architecture (big picture)

- Gemini Analyzer
  - Configures API key (env var or --api-key), uploads the raw video to Google Generative AI, and polls until processing completes.
  - Uses model "models/gemini-2.5-pro" to generate a structured, multi-section analysis from the full video without manual frame extraction.
  - Saves output to {video_stem}_gemini_analysis.txt and deletes the uploaded file from Gemini.
- Gemini Thumbnails
  - Uploads video to Gemini, requests selection of 5–10 distinct high-CTR moments via JSON.
  - Deduplicates results (collapses timestamps <3s apart) and extracts frames using ffmpeg.
  - Saves frames to {video_stem}_thumbnails/ directory, metadata to {video_stem}_thumbnails.json, and appends to {video_stem}_gemini_analysis.txt.

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
./gemini_analyzer.py video.mp4

# Or pass explicitly (not recommended to store in shell history)
./gemini_analyzer.py video.mp4 --api-key {{GEMINI_API_KEY}}
```

Progress Tracking (to stderr):
- **Upload progress**: `Uploading: 12.5 MB / 150 MB (8.3 MB/s)` updates in real-time
- **Processing ETA**: `Processing... (elapsed: 45s, est. 2m remaining)` updates during Gemini analysis
- Heuristic ETA uses file size and upload duration to estimate processing time
- If actual processing exceeds 90% of estimate, ETA adapts upward to avoid misleading remaining time
- Final lines: `Upload complete in X at Y avg` and `Processing complete in Z`

Run: Thumbnail Extraction
```bash
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_thumbnails.py video.mp4
```

Notes
- The local LLaVA-based analyzer has been removed.

## Key file entry points
- gemini_analyzer.py: main() sets up API key and calls analyze_video_gemini using "models/gemini-2.5-pro".
- gemini_thumbnails.py: main() sets up API key and calls select_and_extract_thumbnails, which requests JSON via _generate_with_retry, extracts frames, and manages metadata.

## Output conventions
- Gemini Analysis: {name}_gemini_analysis.txt labeled "GEMINI 2.5 PRO VIDEO ANALYSIS".
- Gemini Thumbnails: {name}_thumbnails/ directory with extracted frames, {name}_thumbnails.json with metadata, and appended section in {name}_gemini_analysis.txt.
