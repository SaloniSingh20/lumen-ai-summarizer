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
    Fetch captions for a YouTube video without downloading it.
    Tries three independent strategies in order; raises RuntimeError only
    after all three have failed.
    """
    import re
    yt_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not yt_match:
        raise RuntimeError("Not a valid YouTube URL")
    video_id = yt_match.group(1)

    # ── Strategy 1: youtube-transcript-api ──────────────────────────────────
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        raw = None
        lang = "en"

        # 1a: English-specific
        try:
            raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        except Exception:
            pass

        # 1b: Any language (covers non-English auto-generated captions)
        if raw is None:
            try:
                raw = YouTubeTranscriptApi.get_transcript(video_id)
            except Exception:
                pass

        # 1c: list_transcripts — prefer auto-generated, fall back to first available
        if raw is None:
            try:
                tlist = YouTubeTranscriptApi.list_transcripts(video_id)
                t = None
                for finder in (
                    lambda tl: tl.find_generated_transcript(["en", "en-US", "en-GB"]),
                    lambda tl: tl.find_manually_created_transcript(["en", "en-US", "en-GB"]),
                    lambda tl: next(iter(tl)),
                ):
                    try:
                        t = finder(tlist)
                        break
                    except Exception:
                        continue
                if t is not None:
                    raw = t.fetch()
                    lang = t.language_code
            except Exception:
                pass  # fall through to strategy 2

        if raw is not None:
            segments = _parse_raw_transcript(raw)
            if segments:
                return segments, lang

    except ImportError:
        pass  # library not installed — try strategy 2

    # ── Strategy 2: yt-dlp --write-auto-subs --skip-download ────────────────
    try:
        return _fetch_subtitles_ytdlp(video_id)
    except Exception as ytdlp_err:
        raise RuntimeError(
            f"YouTube captions unavailable for this video. "
            f"Tried youtube-transcript-api and yt-dlp subtitles — both failed. "
            f"Last error: {ytdlp_err}"
        )


def _parse_raw_transcript(raw) -> list[dict]:
    """Convert youtube-transcript-api raw result (list of dicts or FetchedTranscript) to segments."""
    segments = []
    for item in raw:
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
    return segments


def _fetch_subtitles_ytdlp(video_id: str) -> tuple[list[dict], str]:
    """
    Last-resort: use yt-dlp --skip-download --write-auto-subs to get VTT captions.
    Works for videos where youtube-transcript-api is blocked but yt-dlp auth strategies work.
    """
    import tempfile, glob, re as _re
    tmpdir = tempfile.mkdtemp()
    cmd = [
        "yt-dlp",
        "--write-auto-subs", "--skip-download",
        "--sub-format", "vtt", "--sub-lang", "en.*",
        "--no-check-certificates", "--force-ipv4", "--no-warnings",
        "--extractor-args", "youtube:player_client=tv_embedded",
        "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception:
        raise RuntimeError("yt-dlp subtitle download failed")

    vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
    if not vtt_files:
        raise RuntimeError("No subtitle files found")

    segments: list[dict] = []
    with open(vtt_files[0], encoding="utf-8") as f:
        content = f.read()

    for block in _re.split(r"\n{2,}", content):
        lines = block.strip().splitlines()
        for i, line in enumerate(lines):
            m = _re.match(
                r"(\d+:\d{2}:\d{2}[\.,]\d+|\d+:\d{2}[\.,]\d+)\s*-->\s*(\d+:\d{2}:\d{2}[\.,]\d+|\d+:\d{2}[\.,]\d+)",
                line,
            )
            if m:
                start = _vtt_time(m.group(1))
                end = _vtt_time(m.group(2))
                raw_text = " ".join(lines[i + 1:])
                text = _re.sub(r"<[^>]+>", "", raw_text).strip()
                if text:
                    segments.append({"start": start, "end": end, "text": text})
                break

    if not segments:
        raise RuntimeError("VTT file had no usable captions")
    return segments, "en"


def _vtt_time(s: str) -> float:
    s = s.replace(",", ".")
    parts = s.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(parts[0]) * 60 + float(parts[1])


def fetch_youtube_content(url: str) -> dict:
    """
    Best-effort YouTube content fetcher with a 3-tier fallback chain:
      1. Captions/transcript (youtube-transcript-api / yt-dlp subtitles)
      2. YouTube Data API v3 metadata (title, description, chapters from description)
      3. Scrape og:title / og:description from the watch page (UA-spoofed)

    Always returns whatever could be gathered — raises RuntimeError only when
    NOTHING at all (not even a title) could be retrieved, since at that point
    there is no basis for any summary.
    """
    import re
    yt_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not yt_match:
        raise RuntimeError("Not a valid YouTube URL")
    video_id = yt_match.group(1)

    # ── Tier 1: full transcript/captions ────────────────────────────────────
    try:
        segments, language = fetch_youtube_transcript(url)
        if segments:
            return {
                "segments": segments,
                "language": language,
                "title": None,
                "source": "transcript",
                "partial": False,
            }
    except Exception:
        pass

    # ── Tier 2: YouTube Data API v3 (title, description, chapters) ─────────
    meta = _fetch_youtube_api_metadata(video_id)
    source = "youtube_api"

    # ── Tier 3: scrape og:title / og:description from the watch page ───────
    if not meta:
        meta = _scrape_youtube_page_metadata(video_id)
        source = "scrape"

    if not meta or not (meta.get("title") or meta.get("description")):
        raise RuntimeError(
            "No transcript, captions, or video metadata could be retrieved for this video."
        )

    return {
        "segments": _build_synthetic_segments(meta),
        "language": "en",
        "title": meta.get("title") or None,
        "source": source,
        "partial": True,
    }


def _fetch_youtube_api_metadata(video_id: str) -> "dict | None":
    """Fetch title/description/chapters via the YouTube Data API v3 (requires YOUTUBE_API_KEY)."""
    from ..config import get_settings
    api_key = get_settings().YOUTUBE_API_KEY
    if not api_key:
        return None
    try:
        import httpx
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet,contentDetails", "id": video_id, "key": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items") or []
        if not items:
            return None
        snippet = items[0].get("snippet", {})
        title = (snippet.get("title") or "").strip()
        description = (snippet.get("description") or "").strip()
        if not title and not description:
            return None
        return {
            "title": title,
            "description": description,
            "chapters": _extract_chapters_from_description(description),
        }
    except Exception:
        return None


def _scrape_youtube_page_metadata(video_id: str) -> "dict | None":
    """Last-resort: scrape og:title / og:description from the watch page HTML (UA-spoofed)."""
    try:
        import httpx
        import re as _re
        import html as _html

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = httpx.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers=headers, timeout=20, follow_redirects=True,
        )
        resp.raise_for_status()
        html_text = resp.text

        def _meta(prop: str) -> str:
            m = _re.search(rf'<meta\s+property="{prop}"\s+content="([^"]*)"', html_text)
            return _html.unescape(m.group(1)).strip() if m else ""

        title = _meta("og:title")
        description = _meta("og:description")
        if not title and not description:
            return None
        return {"title": title, "description": description, "chapters": []}
    except Exception:
        return None


def _extract_chapters_from_description(description: str) -> list[dict]:
    """Pull 'MM:SS Label' style chapter markers out of a video description, if present."""
    import re as _re
    chapters = []
    for line in description.splitlines():
        m = _re.match(r"\s*(\d{1,2}(?::\d{2}){1,2})\s*[-–—:]?\s*(.+)", line)
        if m:
            try:
                t = _vtt_time(m.group(1))
            except Exception:
                continue
            label = m.group(2).strip()
            if label:
                chapters.append({"time": t, "label": label})
    return chapters[:30]


def _build_synthetic_segments(meta: dict) -> list[dict]:
    """
    Build a single pseudo-transcript segment from title/description/chapters so the
    existing notes-generation pipeline can produce a best-effort summary from
    metadata alone when no transcript/captions are reachable.
    """
    parts = []
    if meta.get("title"):
        parts.append(f"Video title: {meta['title']}")
    if meta.get("description"):
        parts.append(f"Video description:\n{meta['description'][:4000]}")
    chapters = meta.get("chapters") or []
    if chapters:
        from ..utils.time_parser import format_time as _fmt
        chapter_lines = "\n".join(f"- {_fmt(c['time'])} {c['label']}" for c in chapters)
        parts.append(f"Chapters:\n{chapter_lines}")

    text = (
        "[NOTE: Full transcript/captions were unavailable for this video — YouTube blocked "
        "access from our server. The following is metadata only: title, description, and "
        "chapter list. Base the summary on this information and be transparent that the "
        "full spoken content was not analyzed.]\n\n" + "\n\n".join(parts)
    )
    return [{"start": 0.0, "end": 0.0, "text": text}]


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
