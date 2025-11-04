import sys
import time
from typing import Optional


def human_bytes(n: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024.0:
            return f"{n:.0f} {unit}" if unit == 'B' else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def human_rate(bps: float) -> str:
    return human_bytes(int(bps)) + "/s"


def human_duration(sec: float) -> str:
    sec = max(0, int(round(sec)))
    if sec < 60:
        return f"{sec}s"
    elif sec < 3600:
        m, s = divmod(sec, 60)
        return f"{m}m" if s == 0 else f"{m}m {s}s"
    else:
        h, rem = divmod(sec, 3600)
        m = rem // 60
        return f"{h}h {m:02d}m"


class ProgressPrinter:
    def __init__(self, stream=None, min_interval: float = 0.25):
        self.stream = stream or sys.stderr
        self.min_interval = min_interval
        self._last_t = time.monotonic()
        self._is_tty = self._detect_tty()

    def _detect_tty(self):
        try:
            return self.stream.isatty()
        except Exception:
            return False

    def update_line(self, text: str):
        now = time.monotonic()
        if (now - self._last_t) < self.min_interval:
            return
        self._last_t = now
        if self._is_tty:
            self.stream.write(f"\r{text}".ljust(80))
            self.stream.flush()
        else:
            self.stream.write(text + "\n")
            self.stream.flush()

    def println(self, text: str = ""):
        if self._is_tty and text:
            self.stream.write("\r" + text + "\n")
        else:
            self.stream.write(text + "\n" if text else "\n")
        self.stream.flush()
        self._last_t = time.monotonic()


def initial_processing_estimate(size_bytes: int, upload_duration_s: Optional[float] = None) -> float:
    size_mb = (size_bytes or 0) / 1_000_000.0
    guess_by_size = max(30, min(30 * 60, 30 + 0.8 * size_mb))
    if upload_duration_s is None:
        return guess_by_size
    guess_by_upload = max(20, min(30 * 60, 2.5 * upload_duration_s))
    return (guess_by_size + guess_by_upload) / 2.0