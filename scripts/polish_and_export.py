#!/usr/bin/env python3
"""
Polish highlights video directly with ffmpeg (no Resolve GUI needed):
1. Color grading: Increase saturation, apply subtle contrast boost
2. Audio: Normalize levels, apply light compression
3. Export: Final MP4 optimized for publishing
"""

import subprocess
import os
import sys

INPUT_VIDEO = "/Users/ppt04/Github/video-analyzer/NocturmexMatch3 4K ULTIMATE/compilation/NocturmexMatch3 4K ULTIMATE_highlights_final.mp4"
OUTPUT_DIR = "/Users/ppt04/Github/video-analyzer/NocturmexMatch3 4K ULTIMATE/compilation"
OUTPUT_NAME = "NocturmexMatch3_Highlights_POLISHED.mp4"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, OUTPUT_NAME)

def apply_polish_and_export():
    """Apply color grading and audio normalization via ffmpeg"""
    
    print("="*80)
    print("Highlights Video Polish & Export")
    print("="*80)
    print()
    print(f"Input:  {INPUT_VIDEO}")
    print(f"Output: {OUTPUT_PATH}")
    print()
    
    # FFmpeg filter: color grading + audio normalization
    # Video filters:
    #   - eq: increase saturation (~1.3x) and contrast (0.2 boost)
    #   - hue: optional color shift (0 = neutral)
    #
    # Audio filters:
    #   - dynaudnorm: dynamic audio normalization (like compression + leveling)
    #     gates=-70dB, measure_perchannel=true, peak=0dB (full normalization)
    
    vf = (
        "eq=saturation=1.3:contrast=1.15:brightness=0,"
        "scale=3840:2160:force_original_aspect_ratio=decrease,"
        "pad=3840:2160:(ow-iw)/2:(oh-ih)/2"
    )
    
    af = (
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    )
    
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i", INPUT_VIDEO,
        "-vf", vf,
        "-af", af,
        "-c:v", "hevc_videotoolbox",
        "-q:v", "55",
        "-tag:v", "hvc1",
        "-c:a", "aac",
        "-b:a", "320k",
        "-movflags", "+faststart",
        "-y",
        OUTPUT_PATH
    ]
    
    print("[*] Applying color grading:")
    print("    • Saturation: +30% (1.3x)")
    print("    • Contrast: +15% (1.15x)")
    print("    • Brightness: Neutral")
    print()
    print("[*] Normalizing audio:")
    print("    • Dynamic normalization (gates: -70dB)")
    print("    • Integrated loudness: -16 LUFS")
    print("    • True peak: -1.5 dBFS")
    print()
    print("[*] Encoding settings:")
    print("    • Codec: H.265 (hevc_videotoolbox, Apple Silicon)")
    print("    • Quality: 55 (constant quality)")
    print("    • Audio: AAC, 320 kbps, 48kHz")
    print()
    print("=" * 80)
    print("Starting encode (this may take a few minutes)...")
    print("=" * 80)
    print()
    
    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 80)
        print("✓ Encoding complete!")
        print("=" * 80)
        print()
        print(f"Output file: {OUTPUT_PATH}")
        
        # Check file size
        if os.path.exists(OUTPUT_PATH):
            size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
            print(f"File size: {size_mb:.1f} MB")
        
        print()
        print("Ready to publish to:")
        print("  • OnlyFans")
        print("  • Twitter/X")
        print("  • Other social media platforms")
        print()
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Encoding failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    success = apply_polish_and_export()
    sys.exit(0 if success else 1)
