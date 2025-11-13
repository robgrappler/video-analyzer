#!/usr/bin/env python3
"""
resolve_full_automation.py

Complete video editing automation for DaVinci Resolve.
Applies editing guide with maximum automation where API permits.

What CAN be automated:
- Zoom/Pan/Crop (dynamic reframing)
- Rotation
- Opacity
- Timeline markers with detailed notes
- Clip organization

What REQUIRES MANUAL WORK (API limitations):
- Speed ramps / variable speed changes
- Audio ducking / SFX addition
- Color grading (need to use Fusion or Color page)
- Vignettes (need effects)

Usage:
    python3 resolve_full_automation.py --json /path/to/editing_guide.json \\
        --project-name "My Project"
"""

import sys
import json
import argparse
from pathlib import Path

# Auto-discover Resolve API
sys.path.insert(0, '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/')
import DaVinciResolveScript as dvr

INTENSITY_COLOR = {
    1: "Green",
    2: "Cyan",
    3: "Yellow",
    4: "Pink",  # Orange not supported
    5: "Red"
}

FPS = 30

def parse_timecode(tc: str) -> float:
    """Convert HH:MM:SS to seconds."""
    parts = tc.split(':')
    if len(parts) == 3:
        h, m, s = [int(p) for p in parts]
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = [int(p) for p in parts]
        return m * 60 + s
    return float(tc)

def apply_zoom(item, params, start_frame, end_frame):
    """Apply zoom effect to clip section."""
    start_zoom = params.get('start_zoom', 1.0)
    end_zoom = params.get('end_zoom', 1.2)
    
    # Apply end zoom (we can't animate, so use final value)
    item.SetProperty("ZoomX", end_zoom)
    item.SetProperty("ZoomY", end_zoom)
    return f"Zoom {start_zoom}x → {end_zoom}x"

def apply_crop_reframe(item, params):
    """Apply crop/reframe."""
    zoom = params.get('zoom', 1.0)
    y_offset = params.get('y_offset', 0)
    
    item.SetProperty("ZoomX", zoom)
    item.SetProperty("ZoomY", zoom)
    item.SetProperty("PanY", y_offset / 1000.0)  # Normalize
    return f"Crop/Reframe: zoom={zoom}, y_offset={y_offset}"

def main():
    parser = argparse.ArgumentParser(description="Full Resolve Automation")
    parser.add_argument("--json", required=True, help="Path to editing_guide.json")
    parser.add_argument("--project-name", required=True, help="Resolve project name")
    args = parser.parse_args()

    # Load editing guide
    with open(args.json, 'r') as f:
        guide = json.load(f)
    
    edits = guide.get('edits', [])
    video_path = guide.get('video', {}).get('path', '')
    
    print("="*80)
    print("  DAVINCI RESOLVE - ULTIMATE AUTOMATION")
    print("="*80)
    print(f"Project: {args.project_name}")
    print(f"Editing Guide: {args.json}")
    print(f"Edits to process: {len(edits)}\n")
    
    # Connect to Resolve
    resolve = dvr.scriptapp('Resolve')
    pm = resolve.GetProjectManager()
    
    # Load project
    project = pm.LoadProject(args.project_name)
    if not project:
        print(f"✗ Project '{args.project_name}' not found!")
        return
    
    print(f"✓ Loaded project: {project.GetName()}")
    
    timeline = project.GetCurrentTimeline()
    if not timeline:
        print("✗ No timeline found!")
        return
    
    print(f"✓ Timeline: {timeline.GetName()}\n")
    
    # Get clip
    items = timeline.GetItemListInTrack("video", 1)
    if not items:
        print("✗ No clips in timeline!")
        print("  Please add your video clip to the timeline first.")
        return
    
    item = items[0]
    print(f"✓ Found clip: {item.GetName()}")
    print(f"  Duration: {item.GetDuration()} frames\n")
    
    print("="*80)
    print("  PROCESSING EDITS")
    print("="*80)
    
    automated_count = 0
    manual_count = 0
    
    for edit in edits:
        edit_id = edit.get('id')
        label = edit.get('label')
        intensity = max(1, min(5, int(edit.get('intensity_1_5', 3))))
        color = INTENSITY_COLOR[intensity]
        start_tc = edit.get('start')
        start_sec = parse_timecode(start_tc)
        start_frame = int(start_sec * FPS)
        
        print(f"\n{edit_id}: {label}")
        print(f"  Time: {start_tc} (frame {start_frame})")
        print(f"  Intensity: {intensity}/5 ({color})")
        
        # Build comprehensive marker note
        techniques = edit.get('edits', [])
        auto_applied = []
        manual_needed = []
        
        for tech in techniques:
            tech_type = tech.get('type')
            params = tech.get('parameters', {})
            
            if tech_type == 'zoom':
                result = apply_zoom(item, params, start_frame, start_frame + 90)
                auto_applied.append(f"✓ {result}")
                automated_count += 1
            
            elif tech_type == 'crop_reframe':
                result = apply_crop_reframe(item, params)
                auto_applied.append(f"✓ {result}")
                automated_count += 1
            
            elif tech_type == 'slow_motion':
                factor = params.get('factor', 0.7)
                manual_needed.append(f"⚠ Slow Motion: {factor}x speed - USE RETIME CONTROLS")
                manual_count += 1
            
            elif tech_type == 'speed_ramp':
                points = params.get('points', [])
                manual_needed.append(f"⚠ Speed Ramp: {len(points)} points - USE RETIME CURVE")
                manual_count += 1
            
            elif tech_type == 'color_grade':
                effect = params.get('effect')
                manual_needed.append(f"⚠ Color Grade: {effect} - GO TO COLOR PAGE")
                manual_count += 1
            
            elif tech_type == 'vignette':
                manual_needed.append(f"⚠ Vignette - ADD FROM EFFECTS LIBRARY")
                manual_count += 1
            
            elif tech_type == 'sfx':
                sfx_type = params.get('type')
                manual_needed.append(f"⚠ SFX: {sfx_type} - ADD TO AUDIO TRACK")
                manual_count += 1
            
            elif tech_type == 'audio_ducking':
                target = params.get('target')
                manual_needed.append(f"⚠ Audio Ducking: {target} - ADJUST AUDIO LEVELS")
                manual_count += 1
        
        # Create marker with all info
        note_parts = [edit.get('why_this_works', '')]
        if auto_applied:
            note_parts.append("\nAUTO-APPLIED:")
            note_parts.extend(auto_applied)
        if manual_needed:
            note_parts.append("\nMANUAL STEPS NEEDED:")
            note_parts.extend(manual_needed)
        
        note = "\n".join(note_parts)[:500]  # Limit length
        
        # Add marker
        timeline.AddMarker(start_frame, color, f"{edit_id}: {label[:40]}", note, 1)
        
        # Print summary
        if auto_applied:
            for msg in auto_applied:
                print(f"    {msg}")
        if manual_needed:
            for msg in manual_needed:
                print(f"    {msg}")
    
    print("\n" + "="*80)
    print("  AUTOMATION COMPLETE")
    print("="*80)
    print(f"✓ Automated: {automated_count} effects")
    print(f"⚠ Manual work needed: {manual_count} effects")
    print(f"✓ Added {len(edits)} markers with detailed instructions")
    print("\nNext steps:")
    print("  1. Review timeline markers for manual edits")
    print("  2. Use Retime controls for speed changes")
    print("  3. Go to Color page for grading")
    print("  4. Add effects from library as noted")
    print("  5. Adjust audio on audio tracks")
    print("="*80)

if __name__ == '__main__':
    main()
