#!/usr/bin/env python3
"""
Optimize thumbnail images for web use
Resizes to max 1200px width and compresses to 85% quality
"""

import sys
from pathlib import Path
from PIL import Image

def optimize_image(input_path: Path, output_path: Path, max_width: int = 1200, quality: int = 85):
    """Optimize a single image."""
    try:
        with Image.open(input_path) as img:
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Save with compression
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            
            # Get file sizes
            orig_size = input_path.stat().st_size / 1024
            new_size = output_path.stat().st_size / 1024
            savings = ((orig_size - new_size) / orig_size) * 100
            
            return True, orig_size, new_size, savings
    except Exception as e:
        return False, 0, 0, 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python optimize_thumbnails.py <thumbnails_directory>")
        sys.exit(1)
    
    thumbs_dir = Path(sys.argv[1])
    
    if not thumbs_dir.exists():
        print(f"Error: Directory not found: {thumbs_dir}")
        sys.exit(1)
    
    # Create optimized directory
    optimized_dir = thumbs_dir / "optimized"
    optimized_dir.mkdir(exist_ok=True)
    
    # Find all thumbnails
    thumbnails = sorted(thumbs_dir.glob("thumb_*.jpg"))
    
    if not thumbnails:
        print(f"No thumbnails found in {thumbs_dir}")
        sys.exit(1)
    
    print(f"\n🖼️  Optimizing {len(thumbnails)} images...")
    print(f"   Max width: 1200px | Quality: 85%\n")
    
    total_orig = 0
    total_new = 0
    success_count = 0
    
    for thumb in thumbnails:
        output_path = optimized_dir / thumb.name
        
        success, orig_kb, new_kb, savings = optimize_image(thumb, output_path)
        
        if success:
            success_count += 1
            total_orig += orig_kb
            total_new += new_kb
            print(f"✅ {thumb.name}: {orig_kb:.1f}KB → {new_kb:.1f}KB ({savings:.1f}% savings)")
        else:
            print(f"❌ {thumb.name}: Failed")
    
    if success_count > 0:
        total_savings = ((total_orig - total_new) / total_orig) * 100
        print(f"\n📊 Summary:")
        print(f"   Optimized: {success_count}/{len(thumbnails)} images")
        print(f"   Original: {total_orig:.1f}KB")
        print(f"   Optimized: {total_new:.1f}KB")
        print(f"   Total savings: {total_savings:.1f}%")
        print(f"\n💾 Optimized images saved to: {optimized_dir}")


if __name__ == "__main__":
    main()
