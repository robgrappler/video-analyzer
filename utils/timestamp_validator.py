#!/usr/bin/env python3
"""
Timestamp validation and correction utilities for Gemini video analysis.

Gemini's video analysis sometimes produces inaccurate timestamps. This module
provides tools to validate, flag, and optionally correct suspicious timestamps.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ], capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        print(f"Warning: Could not determine video duration: {e}")
        return 0.0


def validate_timestamp_range(timestamp_s: float, duration_s: float, 
                             margin_s: float = 5.0) -> Tuple[bool, str]:
    """
    Validate that a timestamp falls within video duration.
    
    Returns:
        (is_valid, reason) tuple
    """
    if timestamp_s < 0:
        return False, f"Negative timestamp: {timestamp_s}s"
    if timestamp_s > duration_s + margin_s:
        return False, f"Timestamp {timestamp_s}s exceeds video duration {duration_s}s"
    return True, "OK"


def detect_timestamp_clusters(timestamps: List[float], 
                              min_spacing_s: float = 30.0) -> List[Tuple[int, int]]:
    """
    Detect suspicious clustering of timestamps.
    
    Returns:
        List of (start_index, end_index) for clusters that are too close together
    """
    if len(timestamps) < 2:
        return []
    
    sorted_ts = sorted(enumerate(timestamps), key=lambda x: x[1])
    clusters = []
    cluster_start = 0
    
    for i in range(1, len(sorted_ts)):
        prev_idx, prev_t = sorted_ts[i-1]
        curr_idx, curr_t = sorted_ts[i]
        
        if curr_t - prev_t < min_spacing_s:
            if cluster_start == -1:
                cluster_start = i - 1
        else:
            if cluster_start != -1:
                clusters.append((cluster_start, i - 1))
                cluster_start = -1
    
    if cluster_start != -1:
        clusters.append((cluster_start, len(sorted_ts) - 1))
    
    return clusters


def validate_analysis_timestamps(analysis_json: Dict, video_duration_s: float) -> Dict:
    """
    Validate all timestamps in Gemini analysis JSON.
    
    Returns:
        Validation report with warnings and errors
    """
    report = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "timestamp_count": 0,
        "invalid_count": 0
    }
    
    # Check highlight_moments
    if "highlight_moments" in analysis_json:
        timestamps = []
        for idx, moment in enumerate(analysis_json["highlight_moments"]):
            time_s = moment.get("time_s")
            suggested_s = moment.get("suggested_thumbnail_time_s")
            
            if time_s is not None:
                timestamps.append(time_s)
                report["timestamp_count"] += 1
                is_valid, reason = validate_timestamp_range(time_s, video_duration_s)
                if not is_valid:
                    report["invalid_count"] += 1
                    report["valid"] = False
                    report["errors"].append({
                        "location": f"highlight_moments[{idx}].time_s",
                        "timestamp": time_s,
                        "type": moment.get("type"),
                        "reason": reason
                    })
            
            if suggested_s is not None:
                report["timestamp_count"] += 1
                is_valid, reason = validate_timestamp_range(suggested_s, video_duration_s)
                if not is_valid:
                    report["invalid_count"] += 1
                    report["warnings"].append({
                        "location": f"highlight_moments[{idx}].suggested_thumbnail_time_s",
                        "timestamp": suggested_s,
                        "reason": reason
                    })
        
        # Check for suspicious clustering
        if len(timestamps) >= 3:
            clusters = detect_timestamp_clusters(timestamps, min_spacing_s=20.0)
            if clusters:
                report["warnings"].append({
                    "type": "clustering",
                    "message": f"Found {len(clusters)} timestamp clusters with <20s spacing",
                    "clusters": clusters
                })
    
    # Check momentum_shifts
    if "momentum_shifts" in analysis_json:
        for idx, shift in enumerate(analysis_json["momentum_shifts"]):
            start_s = shift.get("start_s")
            end_s = shift.get("end_s")
            
            if start_s is not None:
                report["timestamp_count"] += 1
                is_valid, reason = validate_timestamp_range(start_s, video_duration_s)
                if not is_valid:
                    report["invalid_count"] += 1
                    report["errors"].append({
                        "location": f"momentum_shifts[{idx}].start_s",
                        "timestamp": start_s,
                        "reason": reason
                    })
            
            if end_s is not None:
                report["timestamp_count"] += 1
                is_valid, reason = validate_timestamp_range(end_s, video_duration_s)
                if not is_valid:
                    report["invalid_count"] += 1
                    report["errors"].append({
                        "location": f"momentum_shifts[{idx}].end_s",
                        "timestamp": end_s,
                        "reason": reason
                    })
            
            if start_s is not None and end_s is not None and start_s >= end_s:
                report["warnings"].append({
                    "location": f"momentum_shifts[{idx}]",
                    "message": f"Start time {start_s}s >= end time {end_s}s"
                })
    
    # Check techniques
    if "techniques" in analysis_json:
        for idx, tech in enumerate(analysis_json["techniques"]):
            start_s = tech.get("start_s")
            end_s = tech.get("end_s")
            
            if start_s is not None:
                report["timestamp_count"] += 1
                is_valid, reason = validate_timestamp_range(start_s, video_duration_s)
                if not is_valid:
                    report["invalid_count"] += 1
                    report["errors"].append({
                        "location": f"techniques[{idx}].start_s",
                        "timestamp": start_s,
                        "name": tech.get("name"),
                        "reason": reason
                    })
            
            if end_s is not None:
                report["timestamp_count"] += 1
                is_valid, reason = validate_timestamp_range(end_s, video_duration_s)
                if not is_valid:
                    report["invalid_count"] += 1
                    report["errors"].append({
                        "location": f"techniques[{idx}].end_s",
                        "timestamp": end_s,
                        "name": tech.get("name"),
                        "reason": reason
                    })
    
    return report


def print_validation_report(report: Dict):
    """Print human-readable validation report."""
    print("\n" + "="*60)
    print("TIMESTAMP VALIDATION REPORT")
    print("="*60)
    print(f"Total timestamps checked: {report['timestamp_count']}")
    print(f"Invalid timestamps: {report['invalid_count']}")
    print(f"Overall status: {'✓ VALID' if report['valid'] else '✗ ERRORS FOUND'}")
    
    if report["errors"]:
        print(f"\n{len(report['errors'])} ERRORS:")
        for err in report["errors"]:
            loc = err.get("location", "unknown")
            ts = err.get("timestamp", "?")
            reason = err.get("reason", "unknown")
            extra = ""
            if "name" in err:
                extra = f" ({err['name']})"
            elif "type" in err:
                extra = f" ({err['type']})"
            print(f"  ✗ {loc}: {ts}s{extra} - {reason}")
    
    if report["warnings"]:
        print(f"\n{len(report['warnings'])} WARNINGS:")
        for warn in report["warnings"]:
            if warn.get("type") == "clustering":
                print(f"  ⚠ {warn['message']}")
            else:
                loc = warn.get("location", "unknown")
                msg = warn.get("message", warn.get("reason", "unknown"))
                print(f"  ⚠ {loc}: {msg}")
    
    print("="*60 + "\n")


def main():
    """CLI for validating analysis JSON timestamps."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate timestamps in Gemini video analysis JSON"
    )
    parser.add_argument("json_file", help="Path to analysis JSON file")
    parser.add_argument("video_file", help="Path to source video file")
    parser.add_argument(
        "--export-report",
        help="Export validation report to JSON file"
    )
    
    args = parser.parse_args()
    
    # Load analysis
    with open(args.json_file, 'r') as f:
        analysis = json.load(f)
    
    # Get video duration
    duration = get_video_duration(args.video_file)
    if duration == 0:
        print("Error: Could not determine video duration")
        return 1
    
    print(f"Video duration: {duration:.1f}s ({duration/60:.1f}m)")
    
    # Validate
    report = validate_analysis_timestamps(analysis, duration)
    
    # Print report
    print_validation_report(report)
    
    # Export if requested
    if args.export_report:
        with open(args.export_report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Validation report exported to: {args.export_report}")
    
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    exit(main())
