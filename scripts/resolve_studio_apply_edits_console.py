#!/usr/bin/env python3
"""
resolve_studio_apply_edits_console.py

Run this script from WITHIN DaVinci Resolve's Script Editor (Python Console).

Steps:
1. Open DaVinci Resolve
2. Go to: Script Editor (or Fusion's Console)
3. Select: Python
4. Copy-paste this script OR click "Open" to load this file
5. Modify the EDITING_GUIDE_JSON path at the bottom
6. Click "Execute" or press Ctrl+Enter

This version works in Resolve's scripting environment where DaVinciResolveScript is available.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# DaVinci Resolve Python API (available in Resolve's Python console)
import DaVinciResolveScript as dvr

# ============================================================================
# CONSTANTS
# ============================================================================

FPS = 30

INTENSITY_COLOR = {
    1: "Green",
    2: "Cyan",
    3: "Yellow",
    4: "Orange",
    5: "Red",
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def parse_timecode_to_seconds(tc: str) -> float:
    """Convert HH:MM:SS or MM:SS or seconds to float seconds."""
    if not tc or tc == "":
        return 0
    
    try:
        return float(tc)
    except ValueError:
        pass
    
    parts = tc.split(":")
    try:
        if len(parts) == 3:
            h, m, s = [int(p) for p in parts]
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = [int(p) for p in parts]
            return m * 60 + s
        elif len(parts) == 1:
            return int(float(parts[0]))
    except (ValueError, IndexError):
        pass
    
    return 0

def seconds_to_frames(seconds: float, fps: int = FPS) -> int:
    """Convert seconds to frame count."""
    return int(round(seconds * fps))

def log(msg: str):
    """Print to console."""
    print(f"[RESOLVE] {msg}")

# ============================================================================
# RESOLVE AUTOMATION
# ============================================================================

def apply_editing_guide(json_path: str, project_name: str = None, dry_run: bool = False):
    """Main function to apply editing guide to Resolve project."""
    
    log("=" * 80)
    log("DaVinci Resolve Studio - Automated Editing Guide Application")
    log("=" * 80)
    
    # Load JSON
    log(f"\n[1] Loading editing guide: {json_path}")
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        log(f"✓ Loaded {len(data.get('edits', []))} edits")
    except Exception as e:
        log(f"✗ Error loading JSON: {e}")
        return
    
    # Get Resolve objects
    log("\n[2] Connecting to Resolve Studio...")
    try:
        resolve = dvr.scriptapp("Resolve")
        pm = resolve.GetProjectManager()
        log("✓ Connected to Resolve")
    except Exception as e:
        log(f"✗ Error connecting: {e}")
        return
    
    # Get or create project
    if not project_name:
        project_name = data.get("video", {}).get("stem", "Editing Guide")
    
    log(f"\n[3] Loading/Creating project: {project_name}")
    try:
        project = pm.LoadProject(project_name)
        if not project:
            project = pm.CreateProject(project_name)
        if project:
            log(f"✓ Project ready: {project.GetName()}")
        else:
            log("✗ Could not get/create project")
            return
    except Exception as e:
        log(f"✗ Error with project: {e}")
        return
    
    # Get timeline
    log("\n[4] Getting timeline...")
    try:
        timeline = project.GetCurrentTimeline()
        if timeline:
            log(f"✓ Timeline: {timeline.GetName()}")
        else:
            # Create empty timeline if none exists
            mp = project.GetMediaPool()
            timeline = mp.CreateEmptyTimeline("Editing Guide")
            log(f"✓ Created timeline: {timeline.GetName()}")
    except Exception as e:
        log(f"✗ Error with timeline: {e}")
        return
    
    # Get clips
    log("\n[5] Getting clips from timeline...")
    clips = []
    try:
        track_count = timeline.GetTrackCount("video")
        for track_idx in range(1, track_count + 1):
            items = timeline.GetItemListInTrack("video", track_idx)
            if items:
                clips.extend(items)
        log(f"✓ Found {len(clips)} clip(s)")
    except Exception as e:
        log(f"✗ Error getting clips: {e}")
        return
    
    if not clips:
        log("⚠ No clips in timeline - import source video first")
        return
    
    # Process edits
    log("\n[6] Processing edits...")
    modifications = 0
    
    edits = data.get("edits", [])
    for edit_idx, edit in enumerate(edits, 1):
        edit_id = edit.get("id", f"E{edit_idx:03d}")
        label = edit.get("label", f"Edit {edit_idx}")
        intensity = max(1, min(5, int(edit.get("intensity_1_5", 3))))
        start_tc = edit.get("start", "00:00:00")
        
        log(f"\n  [{edit_idx}/{len(edits)}] {edit_id}: {label} (intensity {intensity})")
        
        start_sec = parse_timecode_to_seconds(start_tc)
        start_f = seconds_to_frames(start_sec)
        
        # Find matching clip by timecode
        clip = None
        for c in clips:
            try:
                clip_start = c.GetStart()
                if abs(clip_start - start_f) < FPS * 2:  # Within 2 seconds
                    clip = c
                    break
            except:
                pass
        
        if not clip:
            log(f"    ⚠ No clip found at {start_tc}")
            continue
        
        # Apply modifications based on techniques
        for tech in edit.get("edits", []):
            tech_type = tech.get("type", "unknown")
            params = tech.get("parameters", {})
            
            try:
                if tech_type == "slow_motion" and not dry_run:
                    factor = float(params.get("factor", 0.7))
                    clip.SetSpeed(factor)
                    log(f"    ✓ Speed: {factor * 100:.0f}%")
                    modifications += 1
                
                elif tech_type == "speed_ramp" and not dry_run:
                    # Create Fusion comp for speed ramp
                    fusion = clip.AddFusionComp()
                    log(f"    ✓ Fusion speed ramp (add keyframes manually)")
                    modifications += 1
                
                elif tech_type == "zoom" and not dry_run:
                    fusion = clip.AddFusionComp()
                    log(f"    ✓ Fusion zoom comp (configure manually)")
                    modifications += 1
                
                elif tech_type == "color_grade" and not dry_run:
                    fusion = clip.AddFusionComp()
                    log(f"    ✓ Fusion color grade comp (configure manually)")
                    modifications += 1
                
                else:
                    log(f"    • {tech_type}: logged as TODO")
            
            except Exception as e:
                log(f"    ✗ Error applying {tech_type}: {e}")
        
        # Color-code clip by intensity
        try:
            if not dry_run:
                color = INTENSITY_COLOR.get(intensity, "Blue")
                clip.SetColor(color)
                log(f"    ✓ Color: {color}")
                modifications += 1
        except Exception as e:
            log(f"    ✗ Error setting color: {e}")
    
    # Summary
    log("\n" + "=" * 80)
    if dry_run:
        log("DRY RUN - No changes made")
    else:
        log(f"✓ Complete - {modifications} modifications applied")
    log("=" * 80)

# ============================================================================
# MAIN - CONFIGURE AND RUN
# ============================================================================

# ========== EDIT THESE SETTINGS ==========

# Path to your editing_guide.json file
EDITING_GUIDE_JSON = "/Users/ppt04/Github/video-analyzer/Match3Nocturmex25K/editing_guide/Match3Nocturmex25K_editing_guide.json"

# Project name (or leave blank to auto-generate from JSON)
PROJECT_NAME = "Match3 Nocturmex 25K"

# Dry run (True = simulate only, False = apply changes)
DRY_RUN = False

# ========== END SETTINGS ==========

# Run the script
if __name__ == "__main__":
    apply_editing_guide(EDITING_GUIDE_JSON, PROJECT_NAME, DRY_RUN)
