#!/usr/bin/env python3
"""
Extract highlight clips from source video based on Gemini highlights JSON.
Creates individual MP4 clips for each highlight, then generates an ffmpeg concat list.
"""

import json
import subprocess
import os
import sys

HIGHLIGHTS_JSON = "/Users/ppt04/Github/video-analyzer/NocturmexMatch3 4K ULTIMATE/highlights/NocturmexMatch3 4K ULTIMATE_highlights.json"
SRC = "/Users/ppt04/Movies/NocturmexMatch3 4K ULTIMATE.mp4"
WORK_DIR = "/Users/ppt04/Github/video-analyzer/NocturmexMatch3 4K ULTIMATE/compilation"
CLIPS_DIR = os.path.join(WORK_DIR, "clips")

os.makedirs(CLIPS_DIR, exist_ok=True)

# Load highlights JSON
with open(HIGHLIGHTS_JSON, "r") as f:
    data = json.load(f)

segs = data.get("highlights") or data.get("segments") or data

print(f"Found {len(segs)} highlight segments")

# Extract each clip
for idx, seg in enumerate(segs, 1):
    start = seg["start_seconds"]
    end = seg["end_seconds"]
    out = os.path.join(CLIPS_DIR, f"clip_{idx:02d}.mp4")
    
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", str(start),
        "-to", str(end),
        "-i", SRC,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-map", "0",
        "-y", out
    ]
    
    print(f"[{idx}/{len(segs)}] Extracting {out}...")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error extracting clip {idx}: {e}", file=sys.stderr)
        sys.exit(1)

# Build concat list
concat_path = os.path.join(WORK_DIR, "concat_list.txt")
with open(concat_path, "w") as f:
    for idx in range(1, len(segs) + 1):
        p = os.path.join(CLIPS_DIR, f"clip_{idx:02d}.mp4")
        f.write("file '" + p.replace("'", "'\\''") + "'\n")

print(f"\n✓ Wrote concat list to {concat_path}")
print(f"✓ Extracted {len(segs)} clips to {CLIPS_DIR}")
