import sys
import types
import importlib
import contextlib


def install_google_and_ollama_stubs(monkeypatch):
    # Google stubs so imports succeed
    google = types.ModuleType("google")
    genai = types.ModuleType("google.generativeai")
    api_core = types.ModuleType("google.api_core")
    exceptions = types.ModuleType("google.api_core.exceptions")
    exceptions.ResourceExhausted = type("ResourceExhausted", (Exception,), {})
    exceptions.ServiceUnavailable = type("ServiceUnavailable", (Exception,), {})
    exceptions.DeadlineExceeded = type("DeadlineExceeded", (Exception,), {})
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai)
    monkeypatch.setitem(sys.modules, "google.api_core", api_core)
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions)

    # Ollama stub for video_analyzer import
    ollama = types.ModuleType("ollama")
    ollama.chat = lambda *a, **k: {"message": {"content": "ok"}}
    monkeypatch.setitem(sys.modules, "ollama", ollama)


def test_nonexistent_input_handling_gemini_analyzer(monkeypatch, capsys):
    install_google_and_ollama_stubs(monkeypatch)
    sys.modules.pop("gemini_analyzer", None)
    ga = importlib.import_module("gemini_analyzer")

    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    with monkeypatch.context() as m:
        m.setattr(sys, "argv", ["gemini_analyzer.py", "nope.mp4"])
        try:
            ga.main()
            assert False, "Expected SystemExit"
        except SystemExit as e:
            assert e.code == 1
    out = capsys.readouterr().out
    assert "Video file not found" in out


def test_nonexistent_input_handling_gemini_thumbnails(monkeypatch, capsys):
    install_google_and_ollama_stubs(monkeypatch)
    sys.modules.pop("gemini_thumbnails", None)
    gt = importlib.import_module("gemini_thumbnails")

    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    with monkeypatch.context() as m:
        m.setattr(sys, "argv", ["gemini_thumbnails.py", "nope.mp4"])
        try:
            gt.main()
            assert False, "Expected SystemExit"
        except SystemExit as e:
            assert e.code == 1
    out = capsys.readouterr().out
    assert "Video file not found" in out


