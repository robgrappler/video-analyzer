import sys
import types
import importlib
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


def test_gemini_analyzer_success(tmp_path, monkeypatch):
    genai, _ = install_google_stubs(monkeypatch)

    class FileStub:
        def __init__(self, name, state_name):
            self.name = name
            self.state = types.SimpleNamespace(name=state_name)

    deleted = []

    def configure(api_key=None):
        return None

    def upload_file(path=None, **kwargs):
        return FileStub("files/123", "PROCESSING")

    def get_file(name):
        return FileStub(name, "SUCCEEDED")

    def delete_file(name):
        deleted.append(name)

    class Model:
        def __init__(self, name):
            self.name = name

        def generate_content(self, parts, generation_config=None, safety_settings=None):
            return types.SimpleNamespace(text="This is the analysis.")

    genai.configure = configure
    genai.upload_file = upload_file
    genai.get_file = get_file
    genai.delete_file = delete_file
    genai.GenerativeModel = Model

    monkeypatch.chdir(tmp_path)

    # Ensure fresh import
    sys.modules.pop("gemini_analyzer", None)
    gemini_analyzer = importlib.import_module("gemini_analyzer")

    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"")

    gemini_analyzer.analyze_video_gemini(str(video_path), api_key="dummy")

    out_file = tmp_path / "sample" / "analysis" / "sample_gemini_analysis.txt"
    assert out_file.exists()
    content = out_file.read_text()
    assert "GEMINI 2.5 PRO VIDEO ANALYSIS" in content
    assert "This is the analysis." in content
    assert deleted == ["files/123"]
