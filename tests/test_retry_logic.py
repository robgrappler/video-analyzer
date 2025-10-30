import sys
import types
import importlib


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


def test_generate_with_retry_gemini_analyzer(monkeypatch):
    _, exceptions = install_google_stubs(monkeypatch)

    sys.modules.pop("gemini_analyzer", None)
    ga = importlib.import_module("gemini_analyzer")

    calls = {"n": 0}
    sleeps = []

    class Model:
        def generate_content(self, parts, generation_config=None, safety_settings=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ga.ResourceExhausted("Please retry in 3.0s")
            elif calls["n"] == 2:
                raise ga.ServiceUnavailable("temporary")
            elif calls["n"] == 3:
                raise ga.DeadlineExceeded("deadline")
            return "ok"

    monkeypatch.setattr(ga.time, "sleep", lambda t: sleeps.append(t))
    monkeypatch.setattr(ga.random, "uniform", lambda a, b: 0.1)

    res = ga._generate_with_retry(Model(), parts=[])
    assert res == "ok"

    # Expected waits: ~3.3, ~9.35, ~15.895 (jitter 10%)
    assert len(sleeps) == 3
    assert abs(sleeps[0] - 3.3) < 0.05
    assert abs(sleeps[1] - 9.35) < 0.05
    assert abs(sleeps[2] - 15.895) < 0.05


def test_generate_with_retry_gemini_thumbnails(monkeypatch):
    install_google_stubs(monkeypatch)

    sys.modules.pop("gemini_thumbnails", None)
    gt = importlib.import_module("gemini_thumbnails")

    calls = {"n": 0}
    sleeps = []

    class Model:
        def generate_content(self, parts, generation_config=None, safety_settings=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise gt.ResourceExhausted("Please retry in 3.0s")
            elif calls["n"] == 2:
                raise gt.ServiceUnavailable("temporary")
            return "ok"

    monkeypatch.setattr(gt.time, "sleep", lambda t: sleeps.append(t))
    monkeypatch.setattr(gt.random, "uniform", lambda a, b: 0.1)

    res = gt._generate_with_retry(Model(), parts=[])
    assert res == "ok"

    # Expected waits: ~3.3, ~9.35
    assert len(sleeps) == 2
    assert abs(sleeps[0] - 3.3) < 0.05
    assert abs(sleeps[1] - 9.35) < 0.05
