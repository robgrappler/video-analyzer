from pathlib import Path
from typing import Optional, Dict


def get_output_paths(video_path, output_root: Optional[Path] = None) -> Dict[str, Path]:
    video_path = Path(video_path)
    stem = video_path.stem
    root = Path(output_root) if output_root else Path.cwd()
    match_dir = root / stem
    analysis_dir = match_dir / "analysis"
    thumbnails_dir = match_dir / "thumbnails"
    editing_dir = match_dir / "editing_guide"

    # Ensure directories exist
    analysis_dir.mkdir(parents=True, exist_ok=True)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    editing_dir.mkdir(parents=True, exist_ok=True)

    return {
        "root": match_dir,
        "analysis_dir": analysis_dir,
        "thumbnails_dir": thumbnails_dir,
        "editing_guide_dir": editing_dir,
        "analysis_txt": analysis_dir / f"{stem}_gemini_analysis.txt",
        "analysis_json": analysis_dir / f"{stem}_analysis.json",
        "thumbnails_json": thumbnails_dir / f"{stem}_thumbnails.json",
        "editing_txt": editing_dir / f"{stem}_editing_guide.txt",
        "editing_json": editing_dir / f"{stem}_editing_guide.json",
    }