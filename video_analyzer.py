#!/usr/bin/env python3
"""
Uncensored Video Analyzer using LLaVA
Analyzes videos frame-by-frame with temporal context
"""

import os
import sys
import json
import base64
import subprocess
from pathlib import Path
import argparse
import time
import tempfile
import ollama


def extract_frames(video_path, output_dir, fps=1):
    """Extract frames from video at specified FPS"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    frame_pattern = str(output_dir / "frame_%04d.jpg")
    
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",  # High quality
        frame_pattern,
        "-y"  # Overwrite
    ]
    
    print(f"Extracting frames at {fps} FPS...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error extracting frames: {result.stderr}")
        sys.exit(1)
    
    frames = sorted(output_dir.glob("frame_*.jpg"))
    print(f"Extracted {len(frames)} frames")
    return frames


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def analyze_video(video_path, model="llava:34b", fps=0.2, detail_level="medium"):
    """Analyze video with LLaVA using rolling context"""
    
    # Create unique temp directory for frames per run to avoid stale files
    temp_dir = Path(tempfile.mkdtemp(prefix="video_analysis_frames_"))
    frames = extract_frames(video_path, temp_dir, fps)
    
    if not frames:
        print("No frames extracted!")
        return
    
    total_frames = len(frames)
    start_time = time.time()
    
    print(f"\nAnalyzing video with {model}...")
    print("=" * 60)
    
    context = []
    frame_summaries = []
    
    for i, frame_path in enumerate(frames, 1):
        timestamp = (i - 1) / fps
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        print(f"\n[Frame {i}/{len(frames)} - {time_str}]")
        
        # Build prompt with context from previous frame only
        if i == 1:
            prompt = "Describe what's happening in this frame. Be direct and uncensored."
        else:
            last_frame = frame_summaries[-1]  # Only last frame
            last_desc = last_frame.split("] ", 1)[1] if "] " in last_frame else last_frame
            prompt = f"Previous: {last_desc}\n\nNow at {time_str}: What's happening?"
        
        # Read and encode image
        with open(frame_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Call LLaVA via Ollama
        try:
            response = ollama.chat(
                model=model,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [image_data]
                }]
            )
            
            description = response['message']['content']
            frame_summaries.append(f"[{time_str}] {description}")
            print(description)
            
        except Exception as e:
            print(f"Error analyzing frame: {e}")
            
        # Progress / ETA
        elapsed = time.time() - start_time
        avg_per_frame = elapsed / i
        remaining = max(0, (total_frames - i) * avg_per_frame)
        print(f"-- Progress {i}/{total_frames} | Elapsed { _format_duration(elapsed) } | ETA { _format_duration(remaining) }")
            
            
    # Generate final summary
    print("\n" + "=" * 60)
    print("\nGenerating overall video summary...")
    print("=" * 60 + "\n")
    
    all_context = "\n".join(frame_summaries)
    summary_prompt = f"""Summarize this video based on these frame descriptions:

{all_context}

Provide a concise summary of what happens in the video. Be direct and uncensored."""
    
    try:
        response = ollama.chat(
            model=model,
            messages=[{
                'role': 'user',
                'content': summary_prompt
            }]
        )
        
        summary = response['message']['content']
        print(summary)
        
        # Save full analysis
        output_file = Path(video_path).stem + "_analysis.txt"
        with open(output_file, 'w') as f:
            f.write("FRAME-BY-FRAME ANALYSIS\n")
            f.write("=" * 60 + "\n\n")
            f.write("\n\n".join(frame_summaries))
            f.write("\n\n" + "=" * 60 + "\n")
            f.write("OVERALL SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            f.write(summary)
        
        print(f"\n\nFull analysis saved to: {output_file}")
        
    except Exception as e:
        print(f"Error generating summary: {e}")
    
    # Cleanup
    for frame in frames:
        frame.unlink()
    temp_dir.rmdir()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze videos with uncensored LLaVA vision model"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--model", 
        default="llava:34b",
        help="Ollama model to use (default: llava:34b)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--fps",
        type=float,
        help="Frames per second to analyze (mutually exclusive with --interval)"
    )
    group.add_argument(
        "--interval",
        type=float,
        help="Time interval between frames in seconds (mutually exclusive with --fps)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)
    
    if args.interval is not None:
        analysis_fps = 1.0 / args.interval
    elif args.fps is not None:
        analysis_fps = args.fps
    else:
        analysis_fps = 0.2 # Default: 1 frame per 5 seconds

    analyze_video(args.video, model=args.model, fps=analysis_fps)


if __name__ == "__main__":
    main()
