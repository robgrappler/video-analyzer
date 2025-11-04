import sys
import types
import importlib
import json
from pathlib import Path


def install_google_stubs(monkeypatch):
    google = types.ModuleType("google")
    genai = types.ModuleType("google.generativeai")
    api_core = types.ModuleType("google.api_core")
    exceptions = types.ModuleType("google.api_core.exceptions")

    class ResourceExhausted(Exception):
        pass

    class ServiceUnavailable(Exception):
        pass

    class DeadlineExceeded(Exception):
        pass

    exceptions.ResourceExhausted = ResourceExhausted
    exceptions.ServiceUnavailable = ServiceUnavailable
    exceptions.DeadlineExceeded = DeadlineExceeded

    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai)
    monkeypatch.setitem(sys.modules, "google.api_core", api_core)
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions)

    return genai, exceptions


def test_gemini_thumbnails_extraction_and_metadata(tmp_path, monkeypatch):
    genai, _ = install_google_stubs(monkeypatch)

    class FileStub:
        def __init__(self, name, state_name):
            self.name = name
            self.state = types.SimpleNamespace(name=state_name)

    def configure(api_key=None):
        return None

    def upload_file(path=None, **kwargs):
        return FileStub("files/abc", "PROCESSING")

    def get_file(name):
        return FileStub(name, "SUCCEEDED")

    def delete_file(name):
        return None

    # Provide JSON response with near-duplicate timestamps
    items = [
        {"timestamp_seconds": 1, "reason": "A", "suggested_caption": "cap A"},
        {"timestamp_hms": "00:00:02", "reason": "B", "suggested_caption": "cap B"},
        {"timestamp_seconds": 2.1, "reason": "dup", "suggested_caption": "dup"},
        {"timestamp_seconds": 10, "reason": "C", "suggested_caption": "cap C"},
    ]

    class Model:
        def __init__(self, name):
            self.name = name

        def generate_content(self, parts, generation_config=None, safety_settings=None):
            return types.SimpleNamespace(text=json.dumps({"thumbnails": items}))

    genai.configure = configure
    genai.upload_file = upload_file
    genai.get_file = get_file
    genai.delete_file = delete_file
    genai.GenerativeModel = Model

    monkeypatch.chdir(tmp_path)

    # Fresh import
    sys.modules.pop("gemini_thumbnails", None)
    gemini_thumbnails = importlib.import_module("gemini_thumbnails")

    # Stub _extract_frame to create files without calling ffmpeg
    def fake_extract_frame(video_path, ts_seconds, output_dir: Path, index: int):
        output_dir.mkdir(parents=True, exist_ok=True)
        hms = gemini_thumbnails._format_hms(ts_seconds)
        p = output_dir / f"thumb_{index:02d}_{hms.replace(':','-')}.jpg"
        p.write_bytes(b"\xff\xd8\xff\xd9")
        return p

    monkeypatch.setattr(gemini_thumbnails, "_extract_frame", fake_extract_frame)

    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"")

    gemini_thumbnails.select_and_extract_thumbnails(str(video_path), api_key="dummy")

    thumbs_dir = tmp_path / "clip" / "thumbnails"
    files = sorted(thumbs_dir.glob("*.jpg"))
    # Expect deduplication of 2.1s (within 3s of 2s) -> 3 images
    assert len(files) == 3

    meta_file = tmp_path / "clip" / "thumbnails" / "clip_thumbnails.json"
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text())
    assert "thumbnails" in meta and len(meta["thumbnails"]) == 3
    # Ensure image_path exists on disk
    for item in meta["thumbnails"]:
        assert Path(item["image_path"]).exists()

    analysis_file = tmp_path / "clip" / "analysis" / "clip_gemini_analysis.txt"
    assert analysis_file.exists()
    assert "THUMBNAIL PICKS (WRESTLING)" in analysis_file.read_text()
