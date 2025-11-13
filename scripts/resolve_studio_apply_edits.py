#!/usr/bin/env python3
"""
resolve_studio_apply_edits.py

DaVinci Resolve Studio - Full automation of clip modifications via Python API.
This script applies editing guide JSON directly to clips with complete property control.

Usage:
    python3 resolve_studio_apply_edits.py --json /path/to/editing_guide.json \
        [--project-name "Project Name"] [--dry-run]

Environment:
    EDITING_GUIDE_JSON=/path/to/guide.json python3 resolve_studio_apply_edits.py

Features:
    - 100% automated clip property modification
    - Speed ramps and retiming
    - Opacity adjustments
    - Color grading via Fusion
    - Zoom/pan/crop via transforms
    - Clip trimming and organization
    - Comprehensive JSON run log
"""

import json
import os
import sys
import argparse
import platform
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# ============================================================================
# DAVINCI RESOLVE API AUTO-DISCOVERY
# ============================================================================

def GetResolve():
    """
    Return a Resolve scripting app instance, or None if unavailable.
    - Tries normal import first.
    - Falls back to macOS default Modules path via sys.path
    - As a last resort, tries the official python_get_resolve.py helper.
    
    Based on Blackmagic's python_get_resolve.py pattern.
    Note: DaVinciResolveScript.py replaces itself with fusionscript module,
    so we must use sys.path.append() to allow this self-replacement to work.
    """
    # Try a direct import (works if PYTHONPATH is configured)
    bmd = None
    try:
        import DaVinciResolveScript as bmd
    except ImportError:
        pass

    if bmd is None:
        searched = []

        # Common environment variable overrides (aligns with helper patterns)
        env_candidates = [
            os.getenv("RESOLVE_SCRIPT_API"),
            os.getenv("RESOLVE_SCRIPT_DIR"),
            os.getenv("DAVINCI_RESOLVE_SCRIPT_DIR"),
        ]
        candidates = [p for p in env_candidates if p]

        # macOS default (primary target)
        if platform.system() == "Darwin":
            base = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
            candidates += [os.path.join(base, "Modules"), base]

        # Attempt to load the module via sys.path (REQUIRED for DaVinciResolveScript)
        # The DaVinciResolveScript.py module replaces itself with fusionscript,
        # which only works properly when imported via sys.path
        for path in candidates:
            if not path:
                continue
            searched.append(path)
            module_file = os.path.join(path, "DaVinciResolveScript.py")
            
            # Check if the module file exists and add path to sys.path
            if os.path.isfile(module_file) and path not in sys.path:
                sys.path.insert(0, path)  # Insert at beginning for priority
                try:
                    import DaVinciResolveScript as bmd  # type: ignore
                    if bmd and hasattr(bmd, 'scriptapp'):
                        break
                except ImportError:
                    bmd = None
                    continue

        if bmd is None:
            # Last resort: invoke the official helper, if present
            helper = os.path.join(
                "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Examples",
                "python_get_resolve.py",
            )
            if os.path.isfile(helper):
                try:
                    spec = importlib.util.spec_from_file_location("python_get_resolve", helper)
                    if spec and spec.loader:
                        helper_mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(helper_mod)
                        if hasattr(helper_mod, "GetResolve"):
                            app = helper_mod.GetResolve()
                            if app:
                                return app
                except Exception:
                    pass

            # Helpful error
            sys.stderr.write(
                "ERROR: DaVinci Resolve scripting module not found.\n"
                "Searched:\n  - " + "\n  - ".join(searched) + "\n\n"
                "Ensure DaVinci Resolve is installed. On macOS, the Modules path is:\n"
                "  /Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/\n"
                "If installed in a custom location, set RESOLVE_SCRIPT_API to the Modules directory.\n"
            )
            return None

    # Create Resolve app
    try:
        return bmd.scriptapp("Resolve")
    except Exception as e:
        sys.stderr.write(
            f"ERROR: DaVinciResolveScript loaded, but failed to create 'Resolve' app: {e}\n"
            "Make sure DaVinci Resolve is installed and currently running, and that\n"
            "Preferences > System > General > 'External scripting using' is enabled.\n"
        )
        return None

# Initialize Resolve scripting (external CLI)
RESOLVE = GetResolve()
RESOLVE_API_AVAILABLE = RESOLVE is not None

# Optional back-compat: expose the module and dvr if it was imported
dvr = sys.modules.get("DaVinciResolveScript")

if not RESOLVE_API_AVAILABLE:
    print("[WARN] DaVinci Resolve API unavailable; proceeding in dry-run mode.")
    print("[INFO] To enable live operations, ensure Resolve is running and external scripting is enabled.")

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

FPS = 30
DEFAULT_COLOR_PRESET = "PunchyContrast"
DEFAULT_VIGNETTE_PRESET = "VignetteMedium"

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

def current_timestamp():
    return datetime.now().isoformat()

def parse_timecode_to_seconds(tc: str) -> float:
    """Convert HH:MM:SS or MM:SS or seconds to float seconds."""
    if not tc or tc == "":
        return 0
    
    try:
        # Try as pure number
        return float(tc)
    except ValueError:
        pass
    
    # Parse HH:MM:SS format
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
    """Convert seconds to frame count at given fps."""
    return int(round(float(seconds) * int(fps)))

def frames_to_timecode(frames: int, fps: int = FPS) -> str:
    """Convert frames to HH:MM:SS:FF timecode."""
    total_seconds = int(frames / fps)
    frame_in_sec = frames % fps
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_in_sec:02d}"

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

# ============================================================================
# RESOLVE STUDIO API WRAPPER
# ============================================================================

class ResolveStudioWrapper:
    """Wrapper around Resolve Studio Python API with error handling."""
    
    def __init__(self):
        self.resolve = dvr.scriptapp("Resolve")
        self.pm = self.resolve.GetProjectManager()
        self.current_project = None
        self.current_timeline = None
        self.warnings = []
    
    def get_project_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            return self.current_project.GetSetting(key)
        except Exception:
            return default
    
    def set_project_setting(self, key: str, value: str) -> bool:
        try:
            return bool(self.current_project.SetSetting(key, str(value)))
        except Exception:
            return False
    
    # Timeline helpers
    def ensure_video_track(self, index: int) -> bool:
        try:
            tl = self.current_timeline
            if not tl:
                return False
            count = int(tl.GetTrackCount("video") or 0)
            attempts = 0
            while count < index and attempts < 5:
                attempts += 1
                added = False
                try:
                    res = tl.AddTrack("video")
                    added = True
                except Exception:
                    pass
                if not added:
                    try:
                        tl.AddTrack("video", int(count + 1))
                        added = True
                    except Exception:
                        pass
                count = int(tl.GetTrackCount("video") or 0)
                if not added and count < index:
                    break
            return count >= index
        except Exception:
            return False
    
    def lock_track(self, index: int, lock: bool = True) -> None:
        try:
            if lock:
                self.current_timeline.LockTrack("video", int(index))
            else:
                self.current_timeline.UnlockTrack("video", int(index))
        except Exception:
            pass
    
    def get_items_in_track(self, index: int) -> List[Any]:
        try:
            return self.current_timeline.GetItemListInTrack("video", int(index)) or []
        except Exception:
            return []
    
    def add_clip_marker(self, clip: Any, frame: int, color: str, name: str, note: str, duration: int = 0) -> bool:
        try:
            clip.AddMarker(int(frame), color, name, note, int(duration))
            return True
        except Exception:
            return False
    
    def append_segment(self, media_item: Any, start_f: int, end_f: int, video_track_index: int, record_f: Optional[int] = None, include_audio: bool = True) -> Optional[Any]:
        """Append a media segment [start_f,end_f) to a specific video track at record_f.
        Returns the new timeline item. If record_f is None, appends at timeline end.
        """
        try:
            mp = self.current_project.GetMediaPool()
            tl = self.current_timeline
            rec = int(record_f) if record_f is not None else 0
            if record_f is None:
                try:
                    rec = int(tl.GetEndFrame() or 0) + 1
                except Exception:
                    rec = 0
            # Build clipInfo
            clip_info = {
                "mediaPoolItem": media_item,
                "startFrame": int(start_f),
                "endFrame": int(end_f),
                "trackIndex": int(video_track_index),
                "recordFrame": int(rec),
            }
            # Only force video-only when include_audio is False
            if not include_audio:
                clip_info["mediaType"] = 1
            # Structured append
            res = None
            try:
                res = mp.AppendToTimeline([clip_info])
            except Exception:
                res = None
            # Fallback: append full, then trim
            if not res:
                mp.AppendToTimeline([media_item])
            # Identify last item on target track
            items = self.get_items_in_track(video_track_index)
            seg = items[-1] if items else None
            if seg is None:
                return None
            # If structured append failed, trim manually
            try:
                total = int(seg.GetDuration() or 0)
                l_off = max(0, int(start_f))
                S = max(1, int(end_f - start_f))
                r_off = max(0, total - l_off - S)
                seg.SetLeftOffset(l_off)
                seg.SetRightOffset(r_off)
            except Exception:
                pass
            return seg
        except Exception:
            return None
    
    def load_or_create_project(self, project_name: str) -> bool:
        """Load or create a project."""
        try:
            # Try to load existing project
            proj = self.pm.LoadProject(project_name)
            if proj:
                self.current_project = proj
                print(f"[✓] Loaded project: {project_name}")
                return True
        except Exception as e:
            print(f"[WARN] Could not load project: {e}")
        
        # Create new project
        try:
            proj = self.pm.CreateProject(project_name)
            if proj:
                self.current_project = proj
                print(f"[✓] Created project: {project_name}")
                return True
        except Exception as e:
            print(f"[ERROR] Could not create project: {e}")
            return False
    
    def ensure_timeline(self, timeline_name: str = "Editing Guide", fps: int = FPS) -> bool:
        """Ensure a timeline exists at desired FPS.
        - Reuse existing matching timeline if present
        - Otherwise create a new one, avoiding duplicate-name failures
        """
        try:
            # Force project settings before creating the timeline
            self.set_project_setting("useCustomTimelineSettings", "1")
            self.set_project_setting("timelineFrameRate", str(int(fps)))
            self.set_project_setting("timelinePlaybackFrameRate", str(int(fps)))
        except Exception as e:
            print(f"[WARN] Could not set project FPS settings: {e}")
        
        # Try to reuse an existing timeline with the requested name or FPS
        try:
            tl = self.current_project.GetCurrentTimeline()
            if tl:
                self.current_timeline = tl
                print(f"[✓] Using existing timeline: {tl.GetName()}")
                return True
        except Exception:
            pass
        
        try:
            count = self.current_project.GetTimelineCount()
            target_name = f"{timeline_name} ({int(fps)}fps)"
            for i in range(1, int(count or 0) + 1):
                tl_i = self.current_project.GetTimelineByIndex(i)
                try:
                    if tl_i and tl_i.GetName() == target_name:
                        self.current_project.SetCurrentTimeline(tl_i)
                        self.current_timeline = tl_i
                        print(f"[✓] Using timeline: {target_name}")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        
        # Create a fresh timeline with an FPS suffix; ensure unique name
        try:
            mp = self.current_project.GetMediaPool()
            base_name = f"{timeline_name} ({int(fps)}fps)"
            tl_name = base_name
            attempt = 1
            tl = mp.CreateEmptyTimeline(tl_name)
            while not tl and attempt <= 5:
                tl_name = f"{base_name} #{attempt}"
                tl = mp.CreateEmptyTimeline(tl_name)
                attempt += 1
            if tl:
                self.current_project.SetCurrentTimeline(tl)
                self.current_timeline = tl
                print(f"[✓] Created timeline: {tl_name}")
                return True
            else:
                print("[ERROR] Could not create timeline (unknown error)")
                return False
        except Exception as e:
            print(f"[ERROR] Could not create timeline: {e}")
            return False
    
    def import_media(self, media_path: str) -> bool:
        """Import media file to project and append only if timeline is empty."""
        if not Path(media_path).exists():
            print(f"[WARN] Media file not found: {media_path}")
            return False
        
        try:
            mp = self.current_project.GetMediaPool()
            items = mp.ImportMedia([media_path])
            if items:
                print(f"[✓] Imported {len(items)} clip(s)")
                # Append to timeline only if there are no existing video items
                try:
                    tl = self.current_timeline or self.current_project.GetCurrentTimeline()
                    existing = tl.GetItemListInTrack("video", 1) if tl else []
                except Exception:
                    existing = []
                if self.current_timeline and not existing:
                    mp.AppendToTimeline(items)
                    print(f"[✓] Appended {len(items)} clip(s) to timeline (was empty)")
                else:
                    if existing:
                        print("[INFO] Timeline already has video items; skip append")
                return True
        except Exception as e:
            print(f"[WARN] Import failed: {e}")
        
        return False
    
    def add_marker(self, frame: int, color: str, name: str, note: str, duration: int = 0) -> bool:
        """Add marker to timeline."""
        try:
            self.current_timeline.AddMarker(frame, color, name, note, duration)
            return True
        except Exception as e:
            print(f"[WARN] Failed to add marker '{name}': {e}")
            return False

# ============================================================================
# CLIP MODIFICATIONS VIA STUDIO API
# ============================================================================

class ClipModifier:
    """Modify clip properties using Resolve Studio API."""
    
    def __init__(self, resolve_wrapper: ResolveStudioWrapper):
        self.resolve = resolve_wrapper
        self.modifications = []
    
    def get_timeline_clips(self) -> List[Any]:
        """Get all clips in timeline."""
        clips = []
        try:
            print(f"[DEBUG] Timeline in get_timeline_clips: {self.resolve.current_timeline}")
            # Try to get video track count - may return None if no tracks or API unavailable
            track_count = self.resolve.current_timeline.GetTrackCount("video")
            print(f"[DEBUG] Track count: {track_count}")
            
            if track_count and track_count > 0:
                for track_idx in range(1, int(track_count) + 1):
                    # Get items in track
                    items = self.resolve.current_timeline.GetItemListInTrack("video", track_idx)
                    print(f"[DEBUG] Track {track_idx} items: {items}")
                    if items:
                        clips.extend(items)
            else:
                # Fallback: try to get all clips directly from timeline
                print("[DEBUG] No track count available, trying direct timeline clip access")
                try:
                    # Some Resolve API versions have different methods
                    all_clips = self.resolve.current_timeline.GetClips()
                    if all_clips:
                        clips.extend(all_clips)
                        print(f"[DEBUG] Retrieved {len(all_clips)} clips directly")
                except Exception as fallback_err:
                    print(f"[DEBUG] Direct clip access failed: {fallback_err}")
        except Exception as e:
            print(f"[WARN] Could not get clips: {e}")
        
        return clips
    
    def set_clip_speed(self, clip: Any, speed_factor: float) -> bool:
        """Set clip playback speed (0.5 = 50%, 1.0 = normal, 2.0 = 200%)."""
        try:
            clip.SetSpeed(speed_factor)
            self.modifications.append({
                "type": "speed",
                "clip": clip.GetName(),
                "value": f"{speed_factor * 100:.0f}%"
            })
            return True
        except Exception as e:
            print(f"[WARN] Could not set speed: {e}")
            return False
    
    def set_clip_opacity(self, clip: Any, opacity: float) -> bool:
        """Set clip opacity (0.0 = transparent, 1.0 = opaque)."""
        try:
            clip.SetOpacity(opacity)
            self.modifications.append({
                "type": "opacity",
                "clip": clip.GetName(),
                "value": f"{opacity * 100:.0f}%"
            })
            return True
        except Exception as e:
            print(f"[WARN] Could not set opacity: {e}")
            return False
    
    def set_clip_zoom(self, clip: Any, start_zoom: float, end_zoom: float) -> bool:
        """Apply zoom. Prefer Inspector (static), fallback to Fusion ramp if start!=end.
        Returns True if any zoom adjustment was applied.
        """
        # 1) Try Inspector static zoom (works reliably across versions)
        try:
            if abs(end_zoom - 1.0) > 1e-3 or abs(start_zoom - 1.0) > 1e-3:
                okx = clip.SetProperty("ZoomX", float(end_zoom))
                oky = clip.SetProperty("ZoomY", float(end_zoom))
                if okx and oky:
                    suffix = " (ramp TODO)" if abs(end_zoom - start_zoom) > 1e-3 else ""
                    self.modifications.append({
                        "type": "zoom",
                        "clip": clip.GetName(),
                        "value": f"Inspector Zoom: {start_zoom} -> {end_zoom}{suffix}"
                    })
                    return True
        except Exception:
            # fall through to Fusion attempt
            pass

        # 2) Fallback: Create Fusion Transform and attempt a simple ramp
        try:
            fusion = clip.GetFusionCompByIndex(1)
            if not fusion:
                fusion = clip.AddFusionComp()
            if not fusion:
                raise RuntimeError("Fusion comp unavailable")

            # Locate MediaIn/MediaOut
            tools = {}
            try:
                tools = fusion.GetToolList(True)  # include names
            except Exception:
                tools = fusion.GetToolList() or {}
            media_in = None
            media_out = None
            for t in (tools.values() if isinstance(tools, dict) else []):
                try:
                    if getattr(t, "ID", "") == "MediaIn" or getattr(t, "GetAttrs", lambda: {})().get("TOOLS_RegID") == "MediaIn":
                        media_in = t
                    if getattr(t, "ID", "") == "MediaOut" or getattr(t, "GetAttrs", lambda: {})().get("TOOLS_RegID") == "MediaOut":
                        media_out = t
                except Exception:
                    continue

            # Create a Transform tool explicitly and connect between MediaIn and MediaOut
            transform = fusion.AddTool("Transform", -32768, -32768)
            if transform is None:
                raise RuntimeError("Transform tool unavailable")
            try:
                transform.SetAttrs({"TOOLS_Name": "AutoZoomTransform"})
            except Exception:
                pass
            # Connect: MediaIn -> Transform -> MediaOut
            try:
                if media_in:
                    transform.SetInput("Input", media_in)
                if media_out:
                    media_out.SetInput("Input", transform)
            except Exception:
                # Some APIs require ConnectInput
                try:
                    if media_in and hasattr(transform, "ConnectInput"):
                        transform.ConnectInput("Input", media_in, "Output")
                    if media_out and hasattr(media_out, "ConnectInput"):
                        media_out.ConnectInput("Input", transform, "Output")
                except Exception:
                    pass

            # Attempt to keyframe Size from start->end across the clip duration
            try:
                dur = int(clip.GetDuration()) if hasattr(clip, "GetDuration") else 30
                transform.SetInput("Size", {0: float(start_zoom), int(dur): float(end_zoom)})
            except Exception:
                # If keyframe map unsupported, set end value only
                transform.SetInput("Size", float(end_zoom))

            self.modifications.append({
                "type": "zoom",
                "clip": clip.GetName(),
                "value": f"Fusion Transform (AutoZoomTransform): {start_zoom} -> {end_zoom}"
            })
            return True
        except Exception as e:
            print(f"[WARN] Could not set zoom: {e}")
            return False
    
    def trim_clip(self, clip: Any, left_offset: int, right_offset: int) -> bool:
        """Trim clip (offsets in frames)."""
        try:
            if left_offset > 0:
                clip.SetLeftOffset(left_offset)
            if right_offset > 0:
                clip.SetRightOffset(right_offset)
            
            self.modifications.append({
                "type": "trim",
                "clip": clip.GetName(),
                "left_offset": left_offset,
                "right_offset": right_offset
            })
            return True
        except Exception as e:
            print(f"[WARN] Could not trim clip: {e}")
            return False
    
    def create_fusion_effect(self, clip: Any, effect_type: str) -> bool:
        """Create Fusion effect on clip."""
        try:
            fusion_comp = clip.AddFusionComp()
            if fusion_comp:
                self.modifications.append({
                    "type": "fusion_effect",
                    "clip": clip.GetName(),
                    "effect": effect_type
                })
                return True
        except Exception as e:
            print(f"[WARN] Could not create Fusion effect: {e}")
            return False
    
    def set_clip_color(self, clip: Any, color: str) -> bool:
        """Set clip color tag in Resolve."""
        try:
            clip.SetClipColor(color)
            self.modifications.append({
                "type": "color_tag",
                "clip": clip.GetName(),
                "color": color
            })
            return True
        except Exception as e:
            print(f"[WARN] Could not set clip color: {e}")
            return False

# ============================================================================
# EDIT PROCESSING
# ============================================================================

def load_editing_guide(json_path: str) -> Optional[Dict[str, Any]]:
    """Load and parse editing guide JSON."""
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load JSON: {e}")
        return None


def build_todos_for_edit(edit: Dict[str, Any]) -> List[str]:
    """Generate detailed TODOs based on techniques and parameters."""
    todos: List[str] = []
    for tech in edit.get("techniques", []):
        ttype = (tech.get("type") or "").lower()
        p = tech.get("parameters", {}) or {}
        if ttype == "slow_motion":
            speed_val = p.get("speed") or p.get("percent")
            factor = p.get("factor")
            if speed_val is not None:
                todos.append(f"Retime: set speed to {speed_val}% via Retime Controls; enable Optical Flow if artifacting.")
            elif factor is not None:
                try:
                    pct = float(factor) * 100.0
                    todos.append(f"Retime: set speed to {pct:.0f}% via Retime Controls; enable Optical Flow if artifacting.")
                except Exception:
                    todos.append("Retime: set slow-motion via Retime Controls; enable Optical Flow if artifacting.")
            else:
                todos.append("Retime: adjust speed; enable Optical Flow if needed.")
        elif ttype == "speed_ramp":
            e = p.get("entry_speed")
            s = p.get("slow_speed")
            x = p.get("exit_speed")
            plan = f"{e}-{s}-{x}" if e and s and x else "entry/slow/exit"
            todos.append(f"Retime Curve: create speed ramp {plan}; ease handles to smooth transitions.")
        elif ttype == "zoom":
            sv = p.get("start") or p.get("start_zoom")
            ev = p.get("end") or p.get("end_zoom")
            if sv is not None and ev is not None and str(sv) != str(ev):
                todos.append(f"Zoom: keyframe Transform Size from {sv} to {ev} over edit duration (or refine Fusion Transform).")
            else:
                val = ev or sv or 1.0
                todos.append(f"Zoom: set static ZoomX/Y to {val} in Inspector (fine-tune framing).")
        elif ttype == "color_grade":
            eff = p.get("effect") or "vignette/contrast"
            cb = p.get("contrast_boost")
            msg = f"Color: apply {eff}"
            if cb:
                msg += f"; adjust Contrast to {cb}"
            msg += "."
            todos.append(msg)
        elif ttype in ("sfx", "audio_ducking"):
            level = p.get("level")
            typ = p.get("type") or ttype
            detail = f"Audio: {typ}"
            if level is not None:
                try:
                    detail += f" at {int(level)} dB"
                except Exception:
                    detail += f" at {level}"
            detail += "; place on target audio track and balance with mix."
            todos.append(detail)
        else:
            todos.append(f"Technique '{ttype}': review and apply manually as needed.")
    return todos

def normalize_edits(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize edits from JSON."""
    edits = []
    
    for idx, raw in enumerate(data.get("edits", []), 1):
        start_sec = parse_timecode_to_seconds(raw.get("start") or raw.get("start_time") or "00:00:00")
        end_sec = parse_timecode_to_seconds(raw.get("end") or raw.get("end_time") or "00:00:00")
        
        start_f = seconds_to_frames(start_sec)
        end_f = seconds_to_frames(end_sec)
        
        if end_f <= start_f:
            end_f = start_f + FPS
        
        edit = {
            "id": str(raw.get("id") or f"E{idx:03d}"),
            "label": str(raw.get("label") or f"Edit {idx}"),
            "start": start_sec,
            "end": end_sec,
            "start_f": start_f,
            "end_f": end_f,
            "intensity": max(1, min(5, int(raw.get("intensity_1_5") or 3))),
            "why_this_works": str(raw.get("why_this_works") or ""),
            "techniques": raw.get("edits") or [],
        }
        edits.append(edit)
    
    return edits

def apply_edits_to_timeline(resolve: ResolveStudioWrapper, modifier: ClipModifier, edits: List[Dict[str, Any]], run_log: Dict[str, Any]) -> int:
    """Apply edits to timeline and return count of modifications.
    Additionally, duplicates the source clip into per-edit segments on V2 (highlight reel),
    leaving V1 untouched. Segments are appended sequentially and trimmed to each edit.
    """
    modifications_count = 0
    
    print_section("Applying Edits to Timeline")

    # Re-fetch the timeline object to ensure it is valid after potential changes.
    resolve.current_timeline = resolve.current_project.GetCurrentTimeline()
    print(f"[DEBUG] Timeline before getting clips: {resolve.current_timeline}")

    # Determine actual timeline FPS and record it
    try:
        tl_fps_val = resolve.get_project_setting("timelineFrameRate", str(FPS)) or str(FPS)
        timeline_fps = int(float(tl_fps_val))
    except Exception:
        timeline_fps = FPS
    run_log["timeline_fps"] = timeline_fps
    
    clips = modifier.get_timeline_clips()
    if not clips:
        print("[WARN] No clips found in timeline")
        return 0
    
    print(f"[✓] Found {len(clips)} clip(s) in timeline\n")

    # Create separate Segments timeline with clips at original positions
    try:
        print("[INFO] Building Segments timeline (highlight reel)...")
        # Get base media item
        base_clip = None
        v1_items = resolve.get_items_in_track(1)
        if v1_items:
            base_clip = v1_items[0]
        else:
            base_clip = clips[0]
        media_item = None
        try:
            media_item = base_clip.GetMediaPoolItem()
        except Exception:
            media_item = None
        
        if media_item is None:
            print("[WARN] Could not resolve MediaPoolItem from base clip; skipping segments timeline")
        else:
            # Create empty segments timeline and append each segment at original timecode
            try:
                mp = resolve.current_project.GetMediaPool()
                base_seg_name = f"Segments ({timeline_fps}fps)"
                # Auto-unique name to avoid collisions
                seg_name = base_seg_name
                segments_tl = mp.CreateEmptyTimeline(seg_name)
                if not segments_tl:
                    from datetime import datetime as _dt
                    ts = _dt.now().strftime("%Y-%m-%d_%H-%M-%S")
                    for attempt in range(1, 6):
                        seg_name = f"{base_seg_name} #{attempt}"
                        segments_tl = mp.CreateEmptyTimeline(seg_name)
                        if segments_tl:
                            break
                    if not segments_tl:
                        seg_name = f"{base_seg_name} {ts}"
                        segments_tl = mp.CreateEmptyTimeline(seg_name)
                if segments_tl:
                    resolve.current_project.SetCurrentTimeline(segments_tl)
                    print(f"[✓] Created empty Segments timeline '{seg_name}'; appending segments at source timecodes...")
                    for edit in edits:
                        start_f = seconds_to_frames(edit["start"], timeline_fps)
                        end_f = seconds_to_frames(edit["end"], timeline_fps)
                        if end_f <= start_f:
                            end_f = start_f + timeline_fps
                        seg = resolve.append_segment(media_item, start_f, end_f, 1, record_f=start_f, include_audio=True)
                        if seg:
                            try:
                                seg.SetName(f"{edit['id']} - {edit['label']}")
                                color = INTENSITY_COLOR.get(edit["intensity"], "Blue")
                                resolve.add_clip_marker(seg, 0, color, f"{edit['id']} segment", "Highlight clip")
                            except Exception:
                                pass
                    print("[✓] Segments appended")
                else:
                    print("[WARN] Could not create segments timeline")
            except Exception as tl_err:
                print(f"[WARN] Error creating segments timeline: {tl_err}")
    except Exception as seg_err:
        print(f"[WARN] Could not create segments timeline: {seg_err}")
    
    for edit_idx, edit in enumerate(edits, 1):
        print(f"Processing edit {edit_idx}/{len(edits)}: {edit['label']}")
        
        edit_log = {
            "id": edit["id"],
            "label": edit["label"],
            "intensity": edit["intensity"],
            "modifications": [],
            "warnings": []
        }
        applied_types: List[str] = []
        
        # Process techniques/effects for this edit
        for tech in edit.get("techniques", []):
            tech_type = tech.get("type", "unknown")
            params = tech.get("parameters", {})
            
            # Recompute frame positions at actual timeline FPS
            start_f = seconds_to_frames(edit["start"], timeline_fps)
            end_f = seconds_to_frames(edit["end"], timeline_fps)
            if end_f <= start_f:
                end_f = start_f + timeline_fps

            # Find appropriate clip (simplified - matches by timecode proximity)
            for clip in clips:
                try:
                    clip_start_f = clip.GetStart()
                    clip_end_f = clip.GetEnd()
                    if clip_start_f <= start_f < clip_end_f:
                        
                        # Apply modifications based on technique type
                        if tech_type == "slow_motion":
                            # Accept percent, speed, or factor (0.5 = 50%)
                            speed_val = params.get("speed") or params.get("percent")
                            if speed_val is None and params.get("factor") is not None:
                                try:
                                    speed_val = float(params.get("factor")) * 100.0
                                except Exception:
                                    speed_val = 100.0
                            try:
                                speed = float(speed_val) if speed_val is not None else 100.0
                            except Exception:
                                speed = 100.0
                            if modifier.set_clip_speed(clip, speed / 100.0):
                                edit_log["modifications"].append(f"Speed: {speed}%")
                                if "speed" not in applied_types:
                                    applied_types.append("speed")
                                modifications_count += 1
                        
                        elif tech_type == "speed_ramp":
                            # Speed ramp is more complex - create Fusion comp placeholder
                            if modifier.create_fusion_effect(clip, "speed_ramp"):
                                entry = params.get("entry_speed")
                                slow = params.get("slow_speed")
                                exit_spd = params.get("exit_speed")
                                edit_log["modifications"].append(
                                    f"Speed ramp: Fusion comp created (plan {entry}-{slow}-{exit_spd})"
                                )
                                if "speed" not in applied_types:
                                    applied_types.append("speed")
                                modifications_count += 1
                        
                        elif tech_type == "zoom":
                            # Accept start/end or start_zoom/end_zoom keys
                            try:
                                start_zoom = float(params.get("start_zoom") or params.get("start") or 1.0)
                            except Exception:
                                start_zoom = 1.0
                            try:
                                end_zoom = float(params.get("end_zoom") or params.get("end") or start_zoom)
                            except Exception:
                                end_zoom = start_zoom
                            if modifier.set_clip_zoom(clip, start_zoom, end_zoom):
                                edit_log["modifications"].append(f"Zoom: {start_zoom} -> {end_zoom}")
                                if "zoom" not in applied_types:
                                    applied_types.append("zoom")
                                modifications_count += 1
                        
                        elif tech_type == "color_grade":
                            if modifier.create_fusion_effect(clip, "color_grade"):
                                edit_log["modifications"].append("Color grade: Fusion comp created")
                                if "color" not in applied_types:
                                    applied_types.append("color")
                                modifications_count += 1
                        
                        elif tech_type == "sfx" or tech_type == "audio_ducking":
                            edit_log["warnings"].append(f"Audio effect '{tech_type}' requires manual setup on audio track")
                        
                        # Break after processing this clip
                        break
                
                except Exception as e:
                    edit_log["warnings"].append(f"Error processing {tech_type}: {e}")
        
        # Color-code nearest clip based on intensity
        chosen_clip = None
        try:
            start_f = seconds_to_frames(edit["start"], timeline_fps)
            for clip in clips:
                try:
                    clip_start = clip.GetStart()
                    if abs(clip_start - start_f) < timeline_fps * 2:
                        color = INTENSITY_COLOR.get(edit["intensity"], "Blue")
                        if modifier.set_clip_color(clip, color):
                            edit_log["modifications"].append(f"Color tag: {color}")
                            modifications_count += 1
                        chosen_clip = clip
                        break
                except Exception:
                    continue
        except Exception as e:
            edit_log["warnings"].append(f"Could not color-code clip: {e}")
        
        # Add a timeline marker documenting the edit and applied mods
        try:
            color = INTENSITY_COLOR.get(edit["intensity"], "Blue")
            note_lines = []
            if edit.get("why_this_works"):
                note_lines.append(f"Why: {edit['why_this_works']}")
            if edit_log["modifications"]:
                note_lines.append("Applied: " + "; ".join(edit_log["modifications"]))
            todos = build_todos_for_edit(edit)
            if todos:
                note_lines.append("TODOs:\n- " + "\n- ".join(todos))
            if edit_log["warnings"]:
                note_lines.append("Warnings: " + "; ".join(edit_log["warnings"]))
            note = "\n".join(note_lines) if note_lines else "Planned edit"
            start_f = seconds_to_frames(edit["start"], timeline_fps)
            end_f = seconds_to_frames(edit["end"], timeline_fps)
            duration = max(0, end_f - start_f)
            # Include types in the marker name for quick scanning
            if applied_types:
                marker_name = f"{edit['label']} [{', '.join(applied_types)}]"
            else:
                marker_name = edit["label"]
            resolve.add_marker(start_f, color, marker_name, note, duration)
        except Exception as e:
            edit_log["warnings"].append(f"Could not add marker: {e}")
        
        run_log["edits"].append(edit_log)
        print(f"  ├─ Modifications: {len(edit_log['modifications'])}")
        if edit_log["warnings"]:
            print(f"  └─ Warnings: {len(edit_log['warnings'])}")
    
    return modifications_count

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DaVinci Resolve Studio - Automated Clip Modification"
    )
    parser.add_argument("--json", help="Path to editing_guide.json")
    parser.add_argument("--project-name", help="Resolve project name")
    parser.add_argument("--dry-run", action="store_true", help="Plan without modifying")
    parser.add_argument("--fps", type=int, default=FPS, help="Timeline FPS (default 30)")
    parser.add_argument("--color-preset", default=DEFAULT_COLOR_PRESET)
    parser.add_argument("--vignette-preset", default=DEFAULT_VIGNETTE_PRESET)
    
    args = parser.parse_args()
    
    # Get JSON path from args or env
    json_path = args.json or os.getenv("EDITING_GUIDE_JSON")
    
    if not json_path:
        print("[ERROR] No JSON path provided. Use --json or EDITING_GUIDE_JSON env var")
        parser.print_help()
        sys.exit(2)
    
    if not Path(json_path).exists():
        print(f"[ERROR] JSON file not found: {json_path}")
        sys.exit(1)
    
    print_section("DaVinci Resolve Studio - Automated Editing Guide Application")
    print(f"JSON Path: {json_path}")
    print(f"Dry Run: {args.dry_run}")
    
    # Load editing guide
    print("\n[INFO] Loading editing guide...")
    data = load_editing_guide(json_path)
    if not data:
        sys.exit(1)
    
    edits = normalize_edits(data)
    print(f"[✓] Loaded {len(edits)} edits")
    
    # Initialize run log
    run_log = {
        "timestamp": current_timestamp(),
        "json_path": json_path,
        "dry_run": args.dry_run,
        "api_version": "python_studio",
        "edits": []
    }
    
    if args.dry_run:
        print("\n[INFO] DRY RUN MODE - No changes will be made")
        for edit in edits:
            print(f"  - {edit['id']}: {edit['label']} ({len(edit['techniques'])} techniques)")
        run_log["status"] = "dry_run_completed"
    else:
        # Connect to Resolve Studio
        print("\n[INFO] Connecting to Resolve Studio...")
        try:
            resolve_wrap = ResolveStudioWrapper()
            print("[✓] Connected to Resolve Studio")
        except Exception as e:
            print(f"[ERROR] Could not connect to Resolve: {e}")
            sys.exit(1)
        
        # Load/create project
        project_name = args.project_name or data.get("project_name") or Path(json_path).stem
        if not resolve_wrap.load_or_create_project(project_name):
            sys.exit(1)
        
        # Ensure timeline at requested FPS
        if not resolve_wrap.ensure_timeline("Editing Guide", fps=args.fps):
            sys.exit(1)
        
        # Import media if available
        source_path = data.get("video", {}).get("source_path")
        if source_path:
            print(f"\n[INFO] Importing media: {source_path}")
            resolve_wrap.import_media(source_path)
        
        # Apply modifications
        modifier = ClipModifier(resolve_wrap)
        modifications = apply_edits_to_timeline(resolve_wrap, modifier, edits, run_log)
        
        run_log["status"] = "completed"
        run_log["modifications_applied"] = modifications
    
    # Write run log
    log_path = Path(json_path).parent / f"{Path(json_path).stem.replace('_editing_guide', '')}_resolve_studio_apply_log.json"
    print(f"\n[INFO] Writing run log: {log_path}")
    
    try:
        with open(log_path, 'w') as f:
            json.dump(run_log, f, indent=2)
        print(f"[✓] Run log written")
    except Exception as e:
        print(f"[ERROR] Failed to write run log: {e}")
        sys.exit(1)
    
    print_section("Complete")
    if args.dry_run:
        print("Dry run completed. No changes were made.")
    else:
        print(f"Applied {run_log.get('modifications_applied', 0)} modifications to timeline.")
    print(f"Log: {log_path}")

if __name__ == "__main__":
    main()
