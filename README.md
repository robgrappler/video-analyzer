# Uncensored Video Analyzer

Analyze videos using LLaVA 34B vision model with frame-by-frame temporal context understanding.

## Features

- **Truly uncensored** - runs locally with LLaVA
- **Temporal context** - maintains narrative across frames
- **Customizable FPS** - control analysis granularity
- **Full transcripts** - saves detailed frame-by-frame + summary

## Installation

```bash
# Install dependencies
pip install ollama

# Make script executable
chmod +x video_analyzer.py
```

Make sure you have:
- **Ollama** installed with **llava:34b** model
- **ffmpeg** for frame extraction

## Usage

Basic usage (analyzes 1 frame per second):
```bash
./video_analyzer.py /path/to/video.mp4
```

Analyze more frames for detailed content (2 FPS):
```bash
./video_analyzer.py video.mp4 --fps 2
```

Analyze fewer frames for long videos (0.5 FPS = 1 frame every 2 seconds):
```bash
./video_analyzer.py video.mp4 --fps 0.5
```

Use different model:
```bash
./video_analyzer.py video.mp4 --model llava:13b
```

## Output

The script will:
1. Extract frames from video
2. Analyze each frame with temporal context
3. Generate overall video summary
4. Save full analysis to `{video_name}_analysis.txt`

## Performance Notes

- **LLaVA 34B**: Best quality, ~3-5 sec per frame (requires 20GB+ RAM)
- **FPS = 1**: Good for most videos (1 min video = 60 frames)
- **FPS = 0.5**: Better for long videos (1 min video = 30 frames)
- **FPS = 2**: Detailed analysis for short clips

## Example

```bash
./video_analyzer.py sample.mp4 --fps 1
```

This will create `sample_analysis.txt` with complete uncensored analysis.
