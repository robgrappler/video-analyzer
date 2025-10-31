#!/usr/bin/env python3
"""
Video Analyzer using Google Gemini 2.5 Pro
Analyzes full videos natively without frame extraction
"""

import os
import sys
import argparse
from pathlib import Path
import google.generativeai as genai
import re
import time
import random
import io
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded


def _human_bytes(n: int) -> str:
    """Convert bytes to human-readable format (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024.0:
            if unit == 'B':
                return f"{n:.0f} {unit}"
            else:
                return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def _human_rate(bps: float) -> str:
    """Convert bytes per second to human-readable rate (B/s, KB/s, MB/s, GB/s)."""
    return _human_bytes(int(bps)) + "/s"


def _human_duration(sec: float) -> str:
    """Convert seconds to human-readable duration (45s, 2m 3s, 1h 02m)."""
    sec = max(0, int(round(sec)))
    if sec < 60:
        return f"{sec}s"
    elif sec < 3600:
        m, s = divmod(sec, 60)
        if s == 0:
            return f"{m}m"
        else:
            return f"{m}m {s}s"
    else:
        h, rem = divmod(sec, 3600)
        m = rem // 60
        return f"{h}h {m:02d}m"


class ProgressPrinter:
    """Centralized progress printing to stderr with TTY-aware formatting."""
    
    def __init__(self, stream=None, min_interval=0.25):
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
        """Print an inline progress line; use \r for TTY, newline for non-TTY."""
        now = time.monotonic()
        if (now - self._last_t) < self.min_interval:
            return
        self._last_t = now
        
        if self._is_tty:
            # Inline update with carriage return
            self.stream.write(f"\r{text}".ljust(80))  # pad to clear previous line
            self.stream.flush()
        else:
            # Non-TTY: print as separate lines (for CI logs)
            self.stream.write(text + "\n")
            self.stream.flush()
    
    def println(self, text: str = ""):
        """Print a complete line (newline always)."""
        if self._is_tty and text:
            # Clear any inline progress before printing
            self.stream.write("\r" + text + "\n")
        else:
            self.stream.write(text + "\n" if text else "\n")
        self.stream.flush()
        self._last_t = time.monotonic()


class TrackedFile(io.IOBase):
    """File wrapper that tracks bytes read and reports progress."""
    
    def __init__(self, fp, total_bytes, on_progress):
        self._fp = fp
        self.total = total_bytes
        self.on_progress = on_progress
        self.bytes_read = 0
        self._last_report_time = time.monotonic()
        self._last_report_bytes = 0
        self._start = time.monotonic()
    
    def read(self, size=-1):
        chunk = self._fp.read(size)
        if chunk:
            self.bytes_read += len(chunk)
            now = time.monotonic()
            # Report progress if throttle window elapsed or we've finished
            if (now - self._last_report_time) >= 0.25 or self.bytes_read == self.total:
                dt = now - self._last_report_time or 1e-9
                db = self.bytes_read - self._last_report_bytes
                speed = db / dt
                self.on_progress(self.bytes_read, self.total, speed)
                self._last_report_time = now
                self._last_report_bytes = self.bytes_read
        return chunk
    
    def seek(self, *args, **kwargs):
        return self._fp.seek(*args, **kwargs)
    
    def tell(self):
        return self._fp.tell()
    
    def readable(self):
        return True
    
    def seekable(self):
        try:
            return self._fp.seekable()
        except Exception:
            return False
    
    @property
    def name(self):
        return getattr(self._fp, 'name', None)
    
    def close(self):
        return self._fp.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def _parse_retry_delay(exc: Exception) -> float:
    """Try to parse server-suggested retry delay (seconds) from exception text; return -1 if none."""
    s = str(exc)
    # Patterns seen in errors:
    # "Please retry in 4.444884096s." OR protobuf-like retry_delay { seconds: 4 }
    m = re.search(r"retry in\s+([0-9]+\.?[0-9]*)s", s, flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    m = re.search(r"retry_delay\s*\{\s*seconds:\s*([0-9]+)\s*\}", s, flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return -1.0


def _generate_with_retry(model, parts, generation_config=None, safety_settings=None,
                         max_retries: int = 8, initial_delay: float = 5.0, backoff: float = 1.7) -> any:
    """Call model.generate_content with retries on rate limits and transient errors."""
    attempt = 0
    delay = max(0.5, initial_delay)
    while True:
        try:
            return model.generate_content(parts, generation_config=generation_config, safety_settings=safety_settings)
        except ResourceExhausted as e:
            attempt += 1
            if attempt > max_retries:
                raise
            suggested = _parse_retry_delay(e)
            wait = suggested if suggested > 0 else delay
            wait *= (1.0 + random.uniform(0.05, 0.25))
            print(f"Rate limit hit (attempt {attempt}/{max_retries}). Retrying in {wait:.1f}s...")
            time.sleep(wait)
            delay *= backoff
            continue
        except (ServiceUnavailable, DeadlineExceeded) as e:
            attempt += 1
            if attempt > max_retries:
                raise
            wait = delay * (1.0 + random.uniform(0.05, 0.25))
            print(f"Transient error (attempt {attempt}/{max_retries}). Retrying in {wait:.1f}s...")
            time.sleep(wait)
            delay *= backoff
            continue


def analyze_video_gemini(video_path, api_key=None):
    """Analyze video with Gemini 2.5 Pro with progress tracking."""
    
    printer = ProgressPrinter()

    # Configure API key
    if api_key:
        genai.configure(api_key=api_key)
    elif os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        print("Error: GEMINI_API_KEY not set. Use --api-key or set GEMINI_API_KEY environment variable")
        sys.exit(1)

    print(f"Uploading video: {video_path}")

    # Get file size and track upload progress
    try:
        total_bytes = os.path.getsize(video_path)
    except Exception:
        total_bytes = 0
    
    upload_start = time.monotonic()
    upload_end = None
    
    def on_upload_progress(bytes_read, total, speed):
        """Callback for upload progress."""
        progress_text = f"Uploading: {_human_bytes(bytes_read)} / {_human_bytes(total)} ({_human_rate(speed)})"
        printer.update_line(progress_text)
        if bytes_read == total:
            # Upload complete
            nonlocal upload_end
            upload_end = time.monotonic()
            elapsed = upload_end - upload_start
            avg_speed = total / elapsed if elapsed > 0 else 0
            printer.println(f"Upload complete in {_human_duration(elapsed)} at {_human_rate(avg_speed)} avg")

    # Try to upload with tracked file; fallback to direct path if library doesn't support file objects
    try:
        with open(video_path, 'rb') as raw:
            tracked = TrackedFile(raw, total_bytes, on_upload_progress)
            video_file = genai.upload_file(tracked)
    except (TypeError, AttributeError):
        # Fallback: library doesn't accept file-like objects; use direct path
        printer.println("Using direct upload (no progress tracking available)")
        video_file = genai.upload_file(path=video_path)
        upload_end = time.monotonic()
    
    printer.println(f"Uploaded: {video_file.name}")

    # Wait for processing with ETA
    printer.println("Processing video...")
    
    upload_duration = (upload_end - upload_start) if upload_end else 1.0
    size_mb = total_bytes / 1_000_000
    
    # ETA heuristic
    guess_by_size = max(30, min(30 * 60, 30 + 0.8 * size_mb))
    guess_by_upload = max(20, min(30 * 60, 2.5 * upload_duration))
    est_total = (guess_by_size + guess_by_upload) / 2.0
    
    start_time = time.monotonic()
    poll_interval = 1.0
    
    try:
        while video_file.state.name == "PROCESSING":
            elapsed = time.monotonic() - start_time
            # Adapt ETA upward if approaching estimate
            if elapsed >= est_total * 0.9:
                est_total = max(est_total, elapsed * 1.25)
            remaining = max(0.0, est_total - elapsed)
            progress_text = f"Processing... (elapsed: {_human_duration(elapsed)}, est. {_human_duration(remaining)} remaining)"
            printer.update_line(progress_text)
            time.sleep(poll_interval)
            video_file = genai.get_file(video_file.name)
        
        total_elapsed = time.monotonic() - start_time
        printer.println(f"Processing complete in {_human_duration(total_elapsed)}")
    except KeyboardInterrupt:
        printer.println()
        raise

    if video_file.state.name == "FAILED":
        print(f"Video processing failed: {video_file.state}")
        sys.exit(1)

    print("Analyzing video with Gemini 2.5 Pro...")

    # Create model
    model = genai.GenerativeModel("models/gemini-2.5-pro")

    # Analyze video
    prompt = """Analyze this video thoroughly and provide:

1. **Overall Summary**: What happens in the video from start to finish
2. **Key Scenes**: Describe the main scenes and transitions
3. **People/Subjects**: Who or what is featured
4. **Actions**: What activities or events occur
5. **Setting**: Where does this take place
6. **Tone/Style**: The mood and presentation style

Be detailed, direct, and descriptive."""

    try:
        response = _generate_with_retry(model, [video_file, prompt])

        print("\n" + "=" * 60)
        print("VIDEO ANALYSIS")
        print("=" * 60 + "\n")
        print(response.text)

        # Save analysis
        output_file = Path(video_path).stem + "_gemini_analysis.txt"
        with open(output_file, 'w') as f:
            f.write("GEMINI 2.5 PRO VIDEO ANALYSIS\n")
            f.write("=" * 60 + "\n\n")
            f.write(response.text)

        print(f"\n\nAnalysis saved to: {output_file}")
    finally:
        # Cleanup uploaded file
        try:
            genai.delete_file(video_file.name)
            print("Cleaned up uploaded video from Gemini")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Analyze videos with Google Gemini 2.5 Pro"
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--api-key",
        help="Google Gemini API key (or set GEMINI_API_KEY env var)"
    )

    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    analyze_video_gemini(args.video, api_key=args.api_key)


if __name__ == "__main__":
    main()

