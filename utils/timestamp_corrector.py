#!/usr/bin/env python3
"""
Interactive timestamp correction tool for Gemini analysis JSON.

Allows manual review and correction of timestamps that Gemini got wrong.
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional


def format_hms(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    s = int(max(0, round(float(seconds))))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_time_input(time_str: str) -> Optional[float]:
    """
    Parse user time input in various formats:
    - Seconds: "322"
    - MM:SS: "5:22" or "05:22"
    - HH:MM:SS: "0:09:00" or "00:09:00"
    
    Returns seconds or None if invalid.
    """
    time_str = time_str.strip()
    
    # Try parsing as pure seconds first
    try:
        return float(time_str)
    except ValueError:
        pass
    
    # Try parsing as time format
    parts = time_str.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return None
    
    if len(parts) == 3:  # HH:MM:SS
        h, m, s = parts
        return float(h * 3600 + m * 60 + s)
    elif len(parts) == 2:  # MM:SS
        m, s = parts
        return float(m * 60 + s)
    
    return None


def show_highlight_moments(data: Dict, video_duration: float):
    """Display highlight moments with their timestamps."""
    if "highlight_moments" not in data:
        print("No highlight_moments found in JSON.")
        return
    
    moments = data["highlight_moments"]
    print(f"\n{'='*70}")
    print(f"HIGHLIGHT MOMENTS ({len(moments)} total)")
    print(f"Video duration: {format_hms(video_duration)} ({video_duration:.1f}s)")
    print(f"{'='*70}\n")
    
    for idx, moment in enumerate(moments):
        time_s = moment.get("time_s", 0)
        suggested_s = moment.get("suggested_thumbnail_time_s", time_s)
        moment_type = moment.get("type", "unknown")
        hook = moment.get("why_it_hooks", "")
        
        print(f"[{idx}] {moment_type.upper()}")
        print(f"    Time: {format_hms(time_s)} ({time_s}s)")
        print(f"    Thumbnail: {format_hms(suggested_s)} ({suggested_s}s)")
        print(f"    Hook: {hook}")
        print()


def show_techniques(data: Dict, video_duration: float):
    """Display techniques with their timestamps."""
    if "techniques" not in data:
        print("No techniques found in JSON.")
        return
    
    techniques = data["techniques"]
    print(f"\n{'='*70}")
    print(f"TECHNIQUES ({len(techniques)} total)")
    print(f"Video duration: {format_hms(video_duration)} ({video_duration:.1f}s)")
    print(f"{'='*70}\n")
    
    for idx, tech in enumerate(techniques):
        start_s = tech.get("start_s", 0)
        end_s = tech.get("end_s", 0)
        name = tech.get("name", "Unknown")
        tech_type = tech.get("type", "unknown")
        
        print(f"[{idx}] {name} ({tech_type})")
        print(f"    Start: {format_hms(start_s)} ({start_s}s)")
        print(f"    End: {format_hms(end_s)} ({end_s}s)")
        print()


def show_momentum_shifts(data: Dict, video_duration: float):
    """Display momentum shifts with their timestamps."""
    if "momentum_shifts" not in data:
        print("No momentum_shifts found in JSON.")
        return
    
    shifts = data["momentum_shifts"]
    print(f"\n{'='*70}")
    print(f"MOMENTUM SHIFTS ({len(shifts)} total)")
    print(f"Video duration: {format_hms(video_duration)} ({video_duration:.1f}s)")
    print(f"{'='*70}\n")
    
    for idx, shift in enumerate(shifts):
        start_s = shift.get("start_s", 0)
        end_s = shift.get("end_s", 0)
        who = shift.get("who_led", "?")
        why = shift.get("why", "")
        
        print(f"[{idx}] {who} led")
        print(f"    Start: {format_hms(start_s)} ({start_s}s)")
        print(f"    End: {format_hms(end_s)} ({end_s}s)")
        print(f"    Why: {why}")
        print()


def correct_highlight_moment(data: Dict, idx: int, video_duration: float) -> bool:
    """Interactively correct a highlight moment timestamp."""
    if "highlight_moments" not in data or idx >= len(data["highlight_moments"]):
        print(f"Invalid highlight moment index: {idx}")
        return False
    
    moment = data["highlight_moments"][idx]
    current_time = moment.get("time_s", 0)
    current_thumb = moment.get("suggested_thumbnail_time_s", current_time)
    moment_type = moment.get("type", "unknown")
    
    print(f"\nCorrecting highlight moment [{idx}]: {moment_type}")
    print(f"Current time: {format_hms(current_time)} ({current_time}s)")
    print(f"Current thumbnail: {format_hms(current_thumb)} ({current_thumb}s)")
    print(f"Hook: {moment.get('why_it_hooks', '')}")
    
    # Correct main timestamp
    print(f"\nEnter new time (or press Enter to keep {current_time}s):")
    print("Format: seconds (e.g., 540) or MM:SS (e.g., 9:00) or HH:MM:SS")
    new_time_input = input("> ").strip()
    
    if new_time_input:
        new_time = parse_time_input(new_time_input)
        if new_time is None:
            print("Invalid time format. Skipping.")
            return False
        if new_time < 0 or new_time > video_duration + 5:
            print(f"Warning: Time {new_time}s is outside video duration {video_duration}s")
            confirm = input("Continue anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                return False
        moment["time_s"] = int(new_time)
        print(f"✓ Updated time_s to {new_time}s ({format_hms(new_time)})")
    
    # Correct thumbnail timestamp
    print(f"\nEnter new thumbnail time (or press Enter to keep {current_thumb}s):")
    new_thumb_input = input("> ").strip()
    
    if new_thumb_input:
        new_thumb = parse_time_input(new_thumb_input)
        if new_thumb is None:
            print("Invalid time format. Skipping.")
            return False
        if new_thumb < 0 or new_thumb > video_duration + 5:
            print(f"Warning: Time {new_thumb}s is outside video duration {video_duration}s")
        moment["suggested_thumbnail_time_s"] = int(new_thumb)
        print(f"✓ Updated suggested_thumbnail_time_s to {new_thumb}s ({format_hms(new_thumb)})")
    
    return True


def correct_technique(data: Dict, idx: int, video_duration: float) -> bool:
    """Interactively correct a technique timestamp."""
    if "techniques" not in data or idx >= len(data["techniques"]):
        print(f"Invalid technique index: {idx}")
        return False
    
    tech = data["techniques"][idx]
    current_start = tech.get("start_s", 0)
    current_end = tech.get("end_s", 0)
    name = tech.get("name", "Unknown")
    
    print(f"\nCorrecting technique [{idx}]: {name}")
    print(f"Current start: {format_hms(current_start)} ({current_start}s)")
    print(f"Current end: {format_hms(current_end)} ({current_end}s)")
    
    # Correct start timestamp
    print(f"\nEnter new start time (or press Enter to keep {current_start}s):")
    new_start_input = input("> ").strip()
    
    if new_start_input:
        new_start = parse_time_input(new_start_input)
        if new_start is None:
            print("Invalid time format. Skipping.")
            return False
        if new_start < 0 or new_start > video_duration + 5:
            print(f"Warning: Time {new_start}s is outside video duration {video_duration}s")
        tech["start_s"] = int(new_start)
        print(f"✓ Updated start_s to {new_start}s ({format_hms(new_start)})")
    
    # Correct end timestamp
    print(f"\nEnter new end time (or press Enter to keep {current_end}s):")
    new_end_input = input("> ").strip()
    
    if new_end_input:
        new_end = parse_time_input(new_end_input)
        if new_end is None:
            print("Invalid time format. Skipping.")
            return False
        if new_end < 0 or new_end > video_duration + 5:
            print(f"Warning: Time {new_end}s is outside video duration {video_duration}s")
        tech["end_s"] = int(new_end)
        print(f"✓ Updated end_s to {new_end}s ({format_hms(new_end)})")
    
    return True


def correct_momentum_shift(data: Dict, idx: int, video_duration: float) -> bool:
    """Interactively correct a momentum shift timestamp."""
    if "momentum_shifts" not in data or idx >= len(data["momentum_shifts"]):
        print(f"Invalid momentum shift index: {idx}")
        return False
    
    shift = data["momentum_shifts"][idx]
    current_start = shift.get("start_s", 0)
    current_end = shift.get("end_s", 0)
    who = shift.get("who_led", "?")
    
    print(f"\nCorrecting momentum shift [{idx}]: {who} led")
    print(f"Current start: {format_hms(current_start)} ({current_start}s)")
    print(f"Current end: {format_hms(current_end)} ({current_end}s)")
    print(f"Why: {shift.get('why', '')}")
    
    # Correct start timestamp
    print(f"\nEnter new start time (or press Enter to keep {current_start}s):")
    new_start_input = input("> ").strip()
    
    if new_start_input:
        new_start = parse_time_input(new_start_input)
        if new_start is None:
            print("Invalid time format. Skipping.")
            return False
        if new_start < 0 or new_start > video_duration + 5:
            print(f"Warning: Time {new_start}s is outside video duration {video_duration}s")
        shift["start_s"] = int(new_start)
        print(f"✓ Updated start_s to {new_start}s ({format_hms(new_start)})")
    
    # Correct end timestamp
    print(f"\nEnter new end time (or press Enter to keep {current_end}s):")
    new_end_input = input("> ").strip()
    
    if new_end_input:
        new_end = parse_time_input(new_end_input)
        if new_end is None:
            print("Invalid time format. Skipping.")
            return False
        if new_end < 0 or new_end > video_duration + 5:
            print(f"Warning: Time {new_end}s is outside video duration {video_duration}s")
        shift["end_s"] = int(new_end)
        print(f"✓ Updated end_s to {new_end}s ({format_hms(new_end)})")
    
    return True


def interactive_mode(json_path: str, video_duration: float):
    """Run interactive correction mode."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    original_data = json.dumps(data, indent=2)
    modified = False
    
    while True:
        print("\n" + "="*70)
        print("TIMESTAMP CORRECTOR - Interactive Mode")
        print("="*70)
        print("Commands:")
        print("  h  - Show highlight moments")
        print("  t  - Show techniques")
        print("  m  - Show momentum shifts")
        print("  ch <index> - Correct highlight moment")
        print("  ct <index> - Correct technique")
        print("  cm <index> - Correct momentum shift")
        print("  s  - Save changes")
        print("  q  - Quit (prompts to save if modified)")
        print()
        
        cmd = input("> ").strip().lower()
        
        if cmd == 'h':
            show_highlight_moments(data, video_duration)
        elif cmd == 't':
            show_techniques(data, video_duration)
        elif cmd == 'm':
            show_momentum_shifts(data, video_duration)
        elif cmd.startswith('ch '):
            try:
                idx = int(cmd.split()[1])
                if correct_highlight_moment(data, idx, video_duration):
                    modified = True
            except (ValueError, IndexError):
                print("Usage: ch <index>")
        elif cmd.startswith('ct '):
            try:
                idx = int(cmd.split()[1])
                if correct_technique(data, idx, video_duration):
                    modified = True
            except (ValueError, IndexError):
                print("Usage: ct <index>")
        elif cmd.startswith('cm '):
            try:
                idx = int(cmd.split()[1])
                if correct_momentum_shift(data, idx, video_duration):
                    modified = True
            except (ValueError, IndexError):
                print("Usage: cm <index>")
        elif cmd == 's':
            if modified:
                # Backup original
                backup_path = json_path + ".backup"
                with open(backup_path, 'w') as f:
                    f.write(original_data)
                print(f"✓ Backup saved to: {backup_path}")
                
                # Save corrected
                with open(json_path, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"✓ Saved corrections to: {json_path}")
                modified = False
            else:
                print("No modifications to save.")
        elif cmd == 'q':
            if modified:
                save = input("You have unsaved changes. Save before quitting? (y/n): ").strip().lower()
                if save == 'y':
                    backup_path = json_path + ".backup"
                    with open(backup_path, 'w') as f:
                        f.write(original_data)
                    with open(json_path, 'w') as f:
                        json.dump(data, f, indent=2)
                    print(f"✓ Saved to: {json_path}")
            print("Goodbye!")
            break
        else:
            print(f"Unknown command: {cmd}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Interactively correct timestamps in Gemini analysis JSON"
    )
    parser.add_argument("json_file", help="Path to analysis JSON file")
    parser.add_argument(
        "--video-duration",
        type=float,
        help="Video duration in seconds (auto-detected from video_file if provided)"
    )
    parser.add_argument(
        "--video-file",
        help="Path to source video file (for auto-detecting duration)"
    )
    
    args = parser.parse_args()
    
    # Determine video duration
    duration = args.video_duration
    if not duration and args.video_file:
        # Try to auto-detect
        try:
            import subprocess
            res = subprocess.run([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                args.video_file
            ], capture_output=True, text=True, check=True)
            duration = float(res.stdout.strip())
        except Exception as e:
            print(f"Warning: Could not auto-detect video duration: {e}")
    
    if not duration:
        print("Error: Video duration required. Use --video-duration or --video-file")
        return 1
    
    if not Path(args.json_file).exists():
        print(f"Error: JSON file not found: {args.json_file}")
        return 1
    
    interactive_mode(args.json_file, duration)
    return 0


if __name__ == "__main__":
    exit(main())
