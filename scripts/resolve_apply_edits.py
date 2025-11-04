#!/usr/bin/env python3
"""
resolve_apply_edits.py

Translate a Gemini-generated editing_guide.json into DaVinci Resolve (Free) timeline actions.
V1 focuses on: project/timeline creation (30fps), media import/placement, markers, and
best-effort stubs for effect application. Audio SFX/ducking are skipped (TODO markers only).

Usage:
  ./scripts/resolve_apply_edits.py --json /path/to/{stem}_editing_guide.json \
      [--project-name NAME] [--dry-run] \
      [--color-preset PunchyContrast] [--vignette-preset VignetteMedium]

Notes:
- Timecodes in JSON are interpreted relative to timeline start (00:00:00) at 30fps.
- This script aims to be safe: most Resolve API calls are wrapped; failures become TODOs in the log.
- V1 does not guarantee true retime curves; segment-level speed changes are approximations and may be
  logged as TODOs if the API is unavailable in your environment.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FPS = 30
DEFAULT_COLOR_PRESET = "PunchyContrast"
DEFAULT_VIGNETTE_PRESET = "VignetteMedium"


# ---------------------- Time Utilities ----------------------

def hhmmss_to_frames(t: str, fps: int = FPS) -> int:
    t = (t or "0").strip()
    if not t:
        return 0
    # Accept HH:MM:SS or MM:SS or SS
    parts = t.split(":")
    try:
        if len(parts) == 3:
            h, m, s = [int(p) for p in parts]
            total = h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = [int(p) for p in parts]
            total = m * 60 + s
        else:
            total = int(float(parts[0]))
        return int(max(0, round(total * fps)))
    except Exception:
        return 0


def frames_to_tc(frames: int, fps: int = FPS) -> str:
    if frames < 0:
        frames = 0
    s, ff = divmod(frames, fps)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}:{ff:02d}"


# ---------------------- Resolve Bootstrap ----------------------

def _ensure_resolve_paths_in_syspath() -> None:
    candidates = [
        "/Applications/DaVinci Resolve.app/Contents/Libraries/Fusion",
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Lib",
        os.path.expanduser(
            "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
        ),
        os.path.expanduser(
            "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Lib"
        ),
        "/opt/resolve/Developer/Scripting/Modules",
        "/opt/resolve/Developer/Scripting/Lib",
    ]
    for p in candidates:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)


def connect_resolve(dry_run: bool = False):
    """Return (resolve, project_manager) or (None, None) in dry-run/no-API cases."""
    if dry_run:
        return None, None
    try:
        import DaVinciResolveScript as dvr
    except Exception:
        _ensure_resolve_paths_in_syspath()
        try:
            import DaVinciResolveScript as dvr  # type: ignore
        except Exception as e:
            print(f"[WARN] Could not import DaVinciResolveScript: {e}")
            return None, None
    try:
        resolve = dvr.scriptapp("Resolve")  # type: ignore
        pm = resolve.GetProjectManager() if resolve else None
        if not resolve or not pm:
            print("[WARN] Resolve scripting app or ProjectManager not available")
            return None, None
        return resolve, pm
    except Exception as e:
        print(f"[WARN] Failed to connect to Resolve: {e}")
        return None, None


def load_or_create_project(pm, name: str, fps: int = FPS, dry_run: bool = False):
    if dry_run or pm is None:
        return None
    proj = pm.LoadProject(name)
    if proj:
        return proj
    proj = pm.CreateProject(name)
    if not proj:
        print(f"[WARN] Unable to create project '{name}'")
        return None
    # Set frame rate BEFORE creating timeline
    try:
        proj.SetSetting("timelineFrameRate", str(fps))
        proj.SetSetting("timelinePlaybackFrameRate", str(fps))
    except Exception:
        pass
    return proj


def ensure_timeline(project, name: str, fps: int = FPS):
    if not project:
        return None
    try:
        current = project.GetCurrentTimeline()
        if current:
            return current
    except Exception:
        pass
    try:
        # Create an empty timeline named `name`
        mp = project.GetMediaPool()
        tl = mp.CreateEmptyTimeline(name)
        return tl or project.GetCurrentTimeline()
    except Exception as e:
        print(f"[WARN] Failed to create timeline '{name}': {e}")
        return project.GetCurrentTimeline()


def import_clip_and_place(project, video_path: str):
    if not project:
        return None
    try:
        mp = project.GetMediaPool()
        items = mp.ImportMedia([video_path])
        # After import, if there is no timeline or timeline is empty, create from clip
        tl = project.GetCurrentTimeline()
        if tl is None:
            try:
                tl = mp.CreateTimelineFromClips("T1", items)
            except Exception:
                # Fallback: ensure empty timeline exists then append
                tl = ensure_timeline(project, "T1")
                if items:
                    mp.AppendToTimeline(items)
        else:
            # Append to existing timeline
            if items:
                mp.AppendToTimeline(items)
        return project.GetCurrentTimeline()
    except Exception as e:
        print(f"[WARN] Failed to import/place clip: {e}")
        return project.GetCurrentTimeline()


# ---------------------- Data Models ----------------------

@dataclass
class Technique:
    type: str
    parameters: Dict[str, Any]


@dataclass
class EditEntry:
    id: str
    label: str
    start: str
    end: str
    intensity_1_5: int
    edits: List[Technique]
    why_this_works: str
    resolve_hint: Dict[str, Any]
    # Derived
    start_f: int = 0
    end_f: int = 0


@dataclass
class RunLogEdit:
    id: str
    label: str
    type: Optional[str]
    start: str
    end: str
    start_f: int
    end_f: int
    status: str
    actions: List[str]
    warnings: List[str]
    todos: List[str]


# ---------------------- Marker Utilities ----------------------

INTENSITY_COLOR = {
    1: "Green",
    2: "Cyan",
    3: "Yellow",
    4: "Orange",
    5: "Red",
}


def add_timeline_marker(timeline, frame: int, name: str, note: str, color: str = "Blue", duration_frames: int = 0):
    try:
        timeline.AddMarker(frame, color, name, note, duration_frames)
        return True
    except Exception as e:
        print(f"[WARN] Failed to add marker '{name}': {e}")
        return False


# ---------------------- Processing ----------------------

def load_guide(json_path: str) -> Dict[str, Any]:
    with open(json_path, "r") as f:
        return json.load(f)


def normalize_edits(data: Dict[str, Any]) -> List[EditEntry]:
    out: List[EditEntry] = []
    for raw in data.get("edits", []):
        tecs = []
        for e in raw.get("edits", []) or []:
            tecs.append(Technique(type=str(e.get("type", "")), parameters=e.get("parameters", {}) or {}))
        start_f = hhmmss_to_frames(raw.get("start", "00:00:00"))
        end_f = hhmmss_to_frames(raw.get("end", "00:00:00"))
        if end_f <= start_f:
            end_f = start_f + FPS  # ensure at least ~1 second range
        entry = EditEntry(
            id=str(raw.get("id", "")),
            label=str(raw.get("label", "")),
            start=str(raw.get("start", "00:00:00")),
            end=str(raw.get("end", "00:00:00")),
            intensity_1_5=int(raw.get("intensity_1_5", 3)),
            edits=tecs,
            why_this_works=str(raw.get("why_this_works", "")),
            resolve_hint=raw.get("resolve_hint", {}) or {},
            start_f=start_f,
            end_f=end_f,
        )
        out.append(entry)
    # Sort by start time ascending (we'll iterate reverse for application)
    out.sort(key=lambda e: e.start_f)
    return out


def ensure_sidecar_log_path(json_path: str, data: Dict[str, Any]) -> Path:
    json_p = Path(json_path)
    stem = data.get("video", {}).get("stem") or json_p.stem.replace("_editing_guide", "")
    return json_p.parent / f"{stem}_resolve_apply_log.json"


def process_edits(
    timeline,
    edits: List[EditEntry],
    log: Dict[str, Any],
    skip_audio: bool = True,
):
    # Iterate reverse (last to first) to reduce risk of time shifts impacting earlier segments
    for entry in reversed(edits):
        marker_color = INTENSITY_COLOR.get(max(1, min(5, entry.intensity_1_5)), "Blue")
        name = f"{entry.id} {entry.label} (intensity {entry.intensity_1_5})"
        # Marker note: include why + hint/effects
        hint = entry.resolve_hint or {}
        effects_map = hint.get("effects_map") or []
        note_lines = []
        if entry.why_this_works:
            note_lines.append(entry.why_this_works)
        if effects_map:
            try:
                # Truncate to keep marker compact
                em = json.dumps(effects_map, ensure_ascii=False)[:600]
            except Exception:
                em = str(effects_map)[:600]
            note_lines.append(f"effects: {em}")
        note = "\n".join(note_lines)

        actions: List[str] = []
        warnings: List[str] = []
        todos: List[str] = []

        # Add main marker at start
        ok = add_timeline_marker(timeline, entry.start_f, name, note, color=marker_color, duration_frames=0) if timeline else False
        if ok:
            actions.append("marker:start")
        else:
            warnings.append("failed:add_marker_start")

        # Add TODO markers for audio-only ops
        for tech in entry.edits:
            if tech.type in ("sfx", "audio_ducking"):
                if skip_audio:
                    todo_name = f"TODO {entry.id} {tech.type}"
                    try:
                        tnote = json.dumps(tech.parameters, ensure_ascii=False)
                    except Exception:
                        tnote = str(tech.parameters)
                    ok2 = add_timeline_marker(
                        timeline,
                        entry.start_f,
                        todo_name,
                        tnote,
                        color="Purple",
                        duration_frames=max(0, entry.end_f - entry.start_f),
                    ) if timeline else False
                    if ok2:
                        todos.append(f"todo:{tech.type}")
                    else:
                        warnings.append(f"failed:add_todo_marker:{tech.type}")

        # V1: best-effort stubs for visual ops (leave as TODOs if API not available)
        for tech in entry.edits:
            if tech.type in ("slow_motion", "speed_ramp", "zoom", "crop_reframe", "color_grade", "vignette"):
                todos.append(f"apply:{tech.type} (v1 best-effort; may require manual)")

        # Record in run log
        log["edits"].append(
            asdict(
                RunLogEdit(
                    id=entry.id,
                    label=entry.label,
                    type=entry.edits[0].type if entry.edits else None,
                    start=entry.start,
                    end=entry.end,
                    start_f=entry.start_f,
                    end_f=entry.end_f,
                    status="planned_markers_only_v1",
                    actions=actions,
                    warnings=warnings,
                    todos=todos,
                )
            )
        )


# ---------------------- Main ----------------------

def main():
    ap = argparse.ArgumentParser(description="Apply Gemini editing guide to DaVinci Resolve (Free) at 30fps")
    ap.add_argument("--json", required=False, default=None, help="Path to {stem}_editing_guide.json; if omitted in-Resolve, a file picker will appear")
    ap.add_argument("--project-name", default=None, help="Resolve project name (default: {video.stem}_autoedit)")
    ap.add_argument("--dry-run", action="store_true", help="Plan and log without mutating Resolve")
    ap.add_argument("--color-preset", default=DEFAULT_COLOR_PRESET)
    ap.add_argument("--vignette-preset", default=DEFAULT_VIGNETTE_PRESET)
    args = ap.parse_args()

    json_path = args.json or os.getenv("EDITING_GUIDE_JSON")
    if not json_path:
        # Try Resolve-internal file picker if available
        try:
            import DaVinciResolveScript as dvr  # type: ignore
            fusion_app = dvr.scriptapp("Fusion")
            if fusion_app:
                picked = None
                try:
                    picked = fusion_app.RequestFile()
                except Exception:
                    picked = None
                json_path = picked or json_path
        except Exception:
            pass
    if not json_path:
        print("[ERROR] No JSON provided. Use --json, set EDITING_GUIDE_JSON, or run inside Resolve to pick a file.")
        sys.exit(1)

    data = load_guide(json_path)
    video = data.get("video", {})
    stem = video.get("stem") or Path(args.json).stem.replace("_editing_guide", "")
    project_name = args.project_name or f"{stem}_autoedit"

    # Connect to Resolve
    resolve, pm = connect_resolve(dry_run=args.dry_run)
    project = load_or_create_project(pm, project_name, fps=FPS, dry_run=args.dry_run)
    timeline = ensure_timeline(project, "T1", fps=FPS) if project else None

    # Import and place media clip at 00:00:00
    source_path = video.get("source_path")
    if source_path and os.path.exists(source_path):
        timeline = import_clip_and_place(project, source_path) if not args.dry_run else timeline
    else:
        print(f"[WARN] video.source_path missing or not found: {source_path}")

    # Normalize edits
    edits = normalize_edits(data)

    # Prepare run log
    sidecar_path = ensure_sidecar_log_path(json_path, data)
    run_log: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "json_source": os.path.abspath(json_path),
        "project_name": project_name,
        "timeline": "T1",
        "fps": FPS,
        "dry_run": bool(args.dry_run),
        "color_preset": args.color_preset,
        "vignette_preset": args.vignette_preset,
        "edits": [],
        "notes": {
            "audio_ops": "Skipped in v1; TODO markers added for sfx/audio_ducking",
            "visual_ops": "Markers added. Visual effects are left as TODOs in v1 unless implemented later.",
        },
    }

    # Process edits (marker-centric v1)
    process_edits(timeline, edits, run_log, skip_audio=True)

    # Ensure output dir exists
    try:
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Write run log
    with open(sidecar_path, "w") as f:
        json.dump(run_log, f, indent=2)

    print(f"Applied plan (markers + TODOs v1). Log: {sidecar_path}")


if __name__ == "__main__":
    main()
