# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Two analysis tools live here:
- LLaVA Analyzer (video_analyzer.py): local, frame-by-frame analysis via Ollama LLaVA.
- Gemini Analyzer (gemini_analyzer.py): full-video analysis via Google Gemini 2.5 Pro.

## Architecture (big picture)

- LLaVA Analyzer
  - Extracts frames using ffmpeg at a configurable rate (fps or interval).
  - For each frame, builds a prompt with minimal rolling context (previous frame’s summary only) to preserve narrative while constraining tokens.
  - Calls Ollama’s LLaVA with the frame encoded as base64 (ollama.chat with images).
  - Tracks progress/ETA; writes per-frame lines like "[MM:SS] description" and a final overall summary derived from all frame summaries.
  - Uses a unique temp directory per run; cleans up frames afterward. Output: {video_stem}_analysis.txt.
- Gemini Analyzer
  - Configures API key (env var or --api-key), uploads the raw video to Google Generative AI, and polls until processing completes.
  - Uses model "models/gemini-2.5-pro" to generate a structured, multi-section analysis from the full video without manual frame extraction.
  - Saves output to {video_stem}_gemini_analysis.txt and deletes the uploaded file from Gemini.

## Commands (dev/run)

Prereqs
```bash
# Python deps
pip install ollama google-generativeai

# Make scripts runnable (one-time)
chmod +x video_analyzer.py gemini_analyzer.py

# Pull a local model for LLaVA runs
ollama pull llava:34b
```

Run: LLaVA (local)
```bash
# Default detail (0.2 FPS = 1 frame / 5s)
./video_analyzer.py video.mp4

# Higher detail
./video_analyzer.py video.mp4 --fps 2

# Equivalent using interval (seconds per frame)
./video_analyzer.py video.mp4 --interval 5

# Use a different Ollama model
./video_analyzer.py video.mp4 --model llava:13b
```

Run: Gemini 2.5 Pro (cloud)
```bash
# Provide API key via env var (replace with your secret)
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_analyzer.py video.mp4

# Or pass explicitly (not recommended to store in shell history)
./gemini_analyzer.py video.mp4 --api-key {{GEMINI_API_KEY}}
```

Notes
- ffmpeg must be available on PATH for LLaVA analyzer (used for frame extraction).
- LLaVA 34B yields highest quality but is resource intensive; tune --fps for long videos.
- No tests or lint configuration currently exist in this repo.

## Key file entry points
- video_analyzer.py: main() parses --fps or --interval, defaults to 0.2 FPS; analyze_video orchestrates extraction → per-frame analysis → summary → cleanup.
- gemini_analyzer.py: main() sets up API key and calls analyze_video_gemini using "models/gemini-2.5-pro".

## Output conventions
- LLaVA: {name}_analysis.txt with "FRAME-BY-FRAME ANALYSIS" then "OVERALL SUMMARY".
- Gemini: {name}_gemini_analysis.txt labeled "GEMINI 2.5 PRO VIDEO ANALYSIS".