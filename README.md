# Video Analyzer (Gemini)  

Analyze videos using Google Gemini 2.5 Pro models with full‑video understanding. This repository provides a suite of tools for analyzing full videos, extracting high‑impact thumbnails, and generating editing guides targeted at the amateur grappling/wrestling market. All tools run against the Gemini 2.5 Pro cloud models, so no local ML models are required.  

## Features  

- Cloud-based video analysis (no local model required)  
- Full-video structured output, thumbnail extraction, and editing guide generation  
- Real-time upload and processing progress with adaptive ETA  
- Per-video output folder structure: `./{video_name}/` with `analysis/`, `thumbnails/`, and `editing_guide/`
- Orchestrator tool for complete video processing pipeline
- Generates persuasive sales/marketing analytics for wrestling/grappling videos
- WordPress landing page generator with SSH deployment

## Dependencies  

These tools are written in Python 3 and require the following dependencies:  

- `google-generativeai` – official client for Google Generative AI (Gemini 2.5 Pro)  
- `ffmpeg` – used by the thumbnail extractor to pull frames from your video  
- `argparse`, `pathlib`, `json`, `mimetypes` (standard library)  
- A valid Google Gemini API key. You can set the key via the `GEMINI_API_KEY` environment variable or pass it with `--api-key`.

Install the Python dependency via pip:  

```bash  
pip install google-generativeai  
```  

Make sure `ffmpeg` is installed and available on your PATH (`which ffmpeg`).  

## Installation  

Clone this repository and make the Python scripts executable:  

```bash  
git clone https://github.com/robgrappler/video-analyzer.git  
cd video-analyzer  
# install Python dependency  
pip install google-generativeai  
# make scripts executable  
chmod +x gemini_analyzer.py gemini_thumbnails.py gemini_editing_guide.py gemini_core_summary.py gemini_sales_report.py  
```  

Set your Gemini API key once in your environment:  

```bash  
export GEMINI_API_KEY={{GEMINI_API_KEY}}  
```  

Alternatively you can provide the key using the `--api-key` flag on each command, but setting the environment variable is safer since the key won't remain in your shell history.

**Output:** `./{video_name}/analysis/{video_name}_gemini_analysis.txt` labeled "GEMINI 2.5 PRO VIDEO ANALYSIS"

Options:
- `--max-output-tokens` (e.g., 8000–8192)
- `--segment-duration MINUTES` to auto-cover long videos without manual merging (writes a single segmented file)

**Console Output (stderr):
All tools now show real-time progress:
- Upload heartbeat: `Uploading... (elapsed: X)` updates once per second
- Upload summary: `Upload complete in X at Y avg`
- Processing ETA: `Processing... (elapsed: X, est. Y remaining)` (adaptive)
- No flags needed; always verbose

### Core Summary (Minute-by-Minute) — gemini_core_summary.py

Produce a neutral, minute-by-minute core summary.

```bash
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_core_summary.py /path/to/video.mp4 --max-output-tokens 8192
```

**Output:**
- `./{video_name}/analysis/{video_name}_core_summary.txt`

### Wrestling Sales Report — gemini_sales_report.py

Generate the wrestling sales report and JSON metrics only.

```bash
export GEMINI_API_KEY={{GEMINI_API_KEY}}
./gemini_sales_report.py /path/to/video.mp4 --max-output-tokens 8192 --cta-url "https://example.com/buy"
```

**Output:**
- `./{video_name}/analysis/{video_name}_sales_report.txt`
- `./{video_name}/analysis/{video_name}_analysis.json`

### Thumbnail Extraction (gemini_thumbnails.py)

## Usage  

The repository contains multiple CLI tools for comprehensive video analysis and content generation.

### Full Video Analysis (`gemini_analyzer.py`)  

Generates a comprehensive analysis of the entire video. The analysis includes an overall summary, key scenes, people/subjects, actions, setting, tone/style, and (in wrestling mode) sales metrics like match intensity, technical skills, highlight moments, pacing and entertainment value. It supports three modes: `generic`, `wrestling`, or `both`.  

```bash  
# analyze a video in hybrid mode (core summary + wrestling sales report)  
./gemini_analyzer.py /path/to/video.mp4  
# specify a different mode and API key explicitly  
./gemini_analyzer.py /path/to/video.mp4 --mode generic --api-key {{GEMINI_API_KEY}}  
# save extracted JSON to a custom path  
./gemini_analyzer.py /path/to/video.mp4 --json-out analysis.json  
```  

**Outputs:**  

- `./{video_name}_gemini_analysis.txt` – human-readable analysis labelled "GEMINI 2.5 PRO VIDEO ANALYSIS"  
- `./{video_name}_analysis.json` (optional) – structured JSON extracted from the Gemini response when `[BEGIN JSON]` / `[END JSON]` blocks are present  
- Progress information (upload progress, processing ETA) is printed to stderr during the run  

### Thumbnail Extraction (`gemini_thumbnails.py`)  

Selects 8–12 high-CTR moments in the video (with wrestling-specific labels and reasons) and extracts frames using ffmpeg. The script uploads the video to Gemini, requests thumbnail suggestions via JSON, deduplicates timestamps less than 3 seconds apart, and downloads the frames.  

```bash  
./gemini_thumbnails.py /path/to/video.mp4  
```  

**Outputs:**  

- `./{video_name}/thumbnails/` – directory containing extracted thumbnail images  
- `./{video_name}/thumbnails/{video_name}_thumbnails.json` – JSON metadata with timestamps, labels, reasons, suggested captions, `why_high_ctr`, and `crop_hint`  
- Appends a "THUMBNAIL PICKS" section to `./{video_name}/analysis/{video_name}_gemini_analysis.txt`  

### Editing Guide (`gemini_editing_guide.py`)  

Creates an editing guide that identifies high-impact moments for slow motion, zooms, sound effects, colour grading, and other editing actions. The guide is grounded in a marketing psychology document designed for grappling videos. You can optionally provide a previously generated analysis JSON so that edits align with known key moments.  

```bash  
./gemini_editing_guide.py /path/to/video.mp4  
# use an existing analysis JSON to anchor the guide  
./gemini_editing_guide.py /path/to/video.mp4 --analysis-json /path/to/{video_name}_analysis.json  
# control the number of suggested edits and model temperature  
./gemini_editing_guide.py /path/to/video.mp4 --max-edits 20 --temperature 0.2  
```  

**Outputs:**  

- `./{video_name}/editing_guide/{video_name}_editing_guide.txt` – human-readable guide with quick-start instructions and time-coded edit suggestions  
- `./{video_name}/editing_guide/{video_name}_editing_guide.json` – structured JSON (v1) with metadata for potential automation in editors such as DaVinci Resolve  

## Contribution Guidelines  

Contributions are welcome! To propose a change:  

1. [Fork](https://github.com/robgrappler/video-analyzer/fork) this repository and create a feature branch.  
2. Describe your change clearly in the pull request description. Please include motivation, usage examples, and any relevant documentation updates.  
3. Follow [PEP 8](https://peps.python.org/pep-0008/) coding style and add or update tests in the `tests/` directory.  
4. Run existing tests with `pytest` before submitting your PR.  
5. Avoid including any proprietary or explicit content; maintain the safety-focused tone present in the existing prompts.  

Bug reports and feature requests should be filed as [GitHub issues](https://github.com/robgrappler/video-analyzer/issues). Please search existing issues before opening a new one.  

## Roadmap  

- **Packaging & distribution:** Publish the tools to PyPI for easier installation (`pip install video-analyzer`)  
- **GUI/Notebook integration:** Build a simple front-end (possibly using Streamlit or Jupyter) for non-technical users  
- **Model options:** Support additional Gemini models or other open AI models as they become available  
- **Automated editing integration:** Improve the JSON schema for editing guides and add scripts to automatically create project files for editors like DaVinci Resolve  
- **Extended analytics:** Provide optional modules for audience segmentation and A/B testing of thumbnails and titles  

---  

Feel free to suggest improvements or contribute new features via pull requests. This project is evolving, and your feedback helps shape its direction.
