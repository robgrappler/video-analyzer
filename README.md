# Video Analyzer (Gemini)

Analyze videos using Google Gemini 2.5 Pro with full-video understanding.

## Features

- Cloud-based video analysis (no local model required)
- Full-video structured output or thumbnail extraction
- Saves results to `{video_name}_gemini_analysis.txt` and optional thumbnails

## Installation

```bash
# Install dependencies
pip install google-generativeai

# Make scripts executable
chmod +x gemini_analyzer.py gemini_thumbnails.py
```

## Tools

### Full Video Analysis (gemini_analyzer.py)

Generates a comprehensive multi-section analysis of the entire video.

```bash
# Provide your API key via environment variable
export GEMINI_API_KEY={{GEMINI_API_KEY}}

# Run the analyzer
./gemini_analyzer.py /path/to/video.mp4

# Or pass explicitly (not recommended to store in shell history)
./gemini_analyzer.py /path/to/video.mp4 --api-key {{GEMINI_API_KEY}}
```

**Output:** `{video_name}_gemini_analysis.txt` labeled "GEMINI 2.5 PRO VIDEO ANALYSIS"

**Console Output (stderr):**
The analyzer shows real-time progress to stderr:
- Upload progress: bytes transferred, file size, transfer speed
- Processing ETA: elapsed time and estimated remaining time (adaptive)
- No flags needed; always verbose

### Thumbnail Extraction (gemini_thumbnails.py)

Selects 5–10 high-CTR thumbnail moments and extracts frames.

```bash
export GEMINI_API_KEY={{GEMINI_API_KEY}}

# Extract thumbnails
./gemini_thumbnails.py /path/to/video.mp4
```

**Output:**
- `{video_name}_thumbnails/` directory with extracted frames
- `{video_name}_thumbnails.json` with metadata (timestamps, reasons, captions)
- Thumbnail section appended to `{video_name}_gemini_analysis.txt`
