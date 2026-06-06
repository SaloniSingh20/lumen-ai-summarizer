"""Stage 1: Ingest — accept file path or download from URL using yt-dlp."""
import os
import subprocess
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# YouTube videos that consistently fail: age-restricted, DRM-protected music
# videos, private videos, or geo-blocked content. We try multiple strategies.
_COOKIES_FILE = "/cookies/youtube_cookies.txt"

_YT_STRATEGIES = [
    # tv_embedded: most reliable on server IPs in 2026 — no PO token, no nsig
    ["--extractor-args", "youtube:player_client=tv_embedded"],
    # mweb: mobile web client, good fallback
    ["--extractor-args", "youtube:player_client=mweb"],
    # ios: another option that bypasses server IP blocks
    ["--extractor-args", "youtube:player_client=ios"],
    # Last resort: default client
    [],
]


def probe_video(file_path: str) -> dict:
    """Use ffprobe to get duration and stream info."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    data = json.loads(result.stdout)
    duration  = float(data.get("format", {}).get("duration", 0))
    has_video = any(s["codec_type"] == "video" for s in data.get("streams", []))
    has_audio = any(s["codec_type"] == "audio" for s in data.get("streams", []))
    return {"duration": duration, "has_video": has_video, "has_audio_stream": has_audio}


def download_url(url: str, output_dir: str) -> str:
    """
    Download a video from URL using yt-dlp.

    Tries multiple client strategies so restricted videos have a better
    chance of working.  Raises RuntimeError with a human-readable message
    on failure (shown directly in the UI error banner).
    """
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    # Use browser cookies if available — fixes 403 on most YouTube videos.
    # Copy to /tmp first because yt-dlp may try to write back updated cookies,
    # which would fail on a read-only volume mount.
    cookie_args: list[str] = []
    if os.path.exists(_COOKIES_FILE) and os.path.getsize(_COOKIES_FILE) > 50:
        import shutil
        tmp_cookies = "/tmp/yt_cookies_tmp.txt"
        shutil.copy2(_COOKIES_FILE, tmp_cookies)
        cookie_args = ["--cookies", tmp_cookies]

    base_cmd = [
        "yt-dlp",
        "--no-playlist",
        "--format", "best[height<=480][ext=mp4]/best[height<=480]/best[height<=720]/best",
        "-o", output_template,
        "--no-warnings",
        "--socket-timeout", "30",
        "--force-ipv4",          # Render free tier: IPv4 only
        "--no-check-certificates",
    ] + cookie_args

    last_error = ""
    for extra_args in _YT_STRATEGIES:
        cmd = base_cmd + extra_args + [url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            files = [f for f in Path(output_dir).iterdir() if f.is_file()]
            if files:
                return str(max(files, key=lambda f: f.stat().st_mtime))
        last_error = (result.stderr or result.stdout)[-400:]

    # Parse the last error into a helpful message
    raise RuntimeError(_friendly_error(url, last_error))


def _friendly_error(url: str, raw_error: str) -> str:
    """Convert a raw yt-dlp error into a user-friendly message."""
    e = raw_error.lower()

    if "403" in e or "forbidden" in e:
        return (
            "YouTube blocked this video (HTTP 403). "
            "This usually means the video is age-restricted, a DRM-protected music video, "
            "or geo-blocked in the server's region. "
            "Try a different video — lectures, tutorials, or podcasts work best."
        )
    if "private" in e:
        return "This video is private and cannot be downloaded."
    if "not available" in e or "unavailable" in e:
        return "This video is unavailable in the server's region."
    if "sign in" in e or "login" in e:
        return "This video requires a YouTube account to view. Try a publicly accessible video."
    if "copyright" in e or "drm" in e:
        return "This video is DRM-protected and cannot be downloaded."
    if "live" in e:
        return "Live streams cannot be summarized. Try a recorded video."
    if "no video" in e or "no formats" in e:
        return "No downloadable formats found for this URL."

    return (
        f"Could not download the video. "
        f"YouTube error: {raw_error[-200:].strip() or 'unknown'}. "
        "Try a different URL — YouTube tutorials, lectures, or talks work best."
    )


def fetch_youtube_transcript(url: str) -> tuple[list[dict], str]:
    """
    Fetch captions from YouTube's caption API without downloading the video.
    Used as a fallback when yt-dlp is blocked by server IP restrictions.
    Returns (segments, language_code).
    Raises RuntimeError if no transcript is available.
    """
    import re
    yt_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not yt_match:
        raise RuntimeError("Not a valid YouTube URL")
    video_id = yt_match.group(1)

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise RuntimeError("youtube-transcript-api not installed")

    try:
        # Try preferred languages first, then auto-generated, then any available
        raw = None
        lang = "en"
        try:
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        except Exception:
            pass

        # Try any language (auto-generated for non-English videos)
        if raw is None:
            try:
                raw = YouTubeTranscriptApi.get_transcript(video_id)
                lang = "en"
            except Exception:
                pass

        if raw is None:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None
            # Prefer auto-generated (widely available) over manually created
            for finder in (
                lambda t: t.find_generated_transcript(["en", "en-US", "en-GB"]),
                lambda t: t.find_manually_created_transcript(["en", "en-US", "en-GB"]),
                lambda t: next(iter(t)),
            ):
                try:
                    transcript = finder(transcripts)
                    break
                except Exception:
                    continue
            if transcript is None:
                raise RuntimeError("No transcripts found")
            raw = transcript.fetch()
            lang = transcript.language_code

        segments = []
        for item in raw:
            # Support both dict (v0.x) and object (newer API) responses
            if isinstance(item, dict):
                start = float(item.get("start", 0))
                dur   = float(item.get("duration", 1))
                text  = str(item.get("text", "")).strip()
            else:
                start = float(getattr(item, "start", 0))
                dur   = float(getattr(item, "duration", 1))
                text  = str(getattr(item, "text", "")).strip()
            if text:
                segments.append({"start": start, "end": start + dur, "text": text})

        if not segments:
            raise RuntimeError("Transcript is empty")
        return segments, lang
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"YouTube captions unavailable for this video: {e}")


def get_filename_from_url(url: str) -> str:
    """Extract a clean display filename from a URL."""
    import re
    yt_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if yt_match:
        return f"youtube_{yt_match.group(1)}.mp4"
    path = url.split("?")[0].rstrip("/")
    name = path.split("/")[-1] or "video.mp4"
    if "." not in name:
        name += ".mp4"
    return name
