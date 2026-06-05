"""
Robust time-range parser for Lumen queries.
Handles formats like:
  - "10 sec to 20 sec"
  - "0:10-0:20"
  - "1:30 to 2:00"
  - "from 90s to 120s"
  - "minute 2"
  - "the beginning" / "the end" (requires video duration)
  - "last 30 seconds"
  - "first minute"
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class TimeRange:
    start: float
    end: float


def parse_time_token(token: str) -> Optional[float]:
    """
    Parse a single time token to seconds.
    Supports: "30s", "30 sec", "1:30", "1m30s", "1 minute", "90", etc.
    """
    token = token.strip().lower()
    if not token:
        return None

    # HH:MM:SS or MM:SS
    colon_match = re.fullmatch(r"(\d+):(\d{2})(?::(\d{2}))?", token)
    if colon_match:
        parts = [int(x) for x in colon_match.groups() if x is not None]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]

    # Combined: "1m30s", "1m 30s", "1min 30sec"
    combined = re.fullmatch(r"(\d+)\s*m(?:in(?:ute)?s?)?\s*(\d+)\s*s(?:ec(?:ond)?s?)?", token)
    if combined:
        return int(combined.group(1)) * 60 + int(combined.group(2))

    # Pure minutes: "2m", "2min", "2 minutes", "minute 2"
    min_match = re.fullmatch(r"(?:minute\s+)?(\d+)\s*m(?:in(?:ute)?s?)?|(\d+)\s+min(?:ute)?s?", token)
    if min_match:
        val = min_match.group(1) or min_match.group(2)
        return int(val) * 60

    # "minute N" format
    min_n = re.fullmatch(r"minute\s+(\d+)", token)
    if min_n:
        return int(min_n.group(1)) * 60

    # Pure seconds: "30s", "30sec", "30 seconds"
    sec_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?", token)
    if sec_match:
        return float(sec_match.group(1))

    # Plain number (assume seconds)
    plain = re.fullmatch(r"(\d+(?:\.\d+)?)", token)
    if plain:
        return float(plain.group(1))

    return None


def parse_time_range(text: str, video_duration: Optional[float] = None) -> Optional[TimeRange]:
    """
    Parse a time range from a natural language query.
    Returns TimeRange(start, end) in seconds, or None if no range detected.
    """
    text_lower = text.lower().strip()

    # "the beginning" / "the start" / "the intro"
    if re.search(r"\b(the\s+)?(beginning|start|intro|opening)\b", text_lower):
        end = min(30.0, video_duration * 0.15) if video_duration else 30.0
        return TimeRange(0.0, end)

    # "the end" / "the outro" / "the conclusion"
    if re.search(r"\b(the\s+)?(end|outro|conclusion|last part|final)\b", text_lower):
        if video_duration:
            start = max(0.0, video_duration - 30.0)
            return TimeRange(start, video_duration)
        return None

    # "last N seconds/minutes"
    last_match = re.search(r"last\s+(\d+(?:\.\d+)?)\s*(s(?:ec(?:ond)?s?)?|m(?:in(?:ute)?s?)?)", text_lower)
    if last_match and video_duration:
        val = float(last_match.group(1))
        unit = last_match.group(2)
        dur_secs = val * 60 if unit.startswith("m") else val
        start = max(0.0, video_duration - dur_secs)
        return TimeRange(start, video_duration)

    # "first minute" / "first hour" (without a number)
    bare_first = re.search(r"\bfirst\s+(minute|hour|second)\b", text_lower)
    if bare_first:
        unit_map = {"minute": 60.0, "hour": 3600.0, "second": 1.0}
        return TimeRange(0.0, unit_map[bare_first.group(1)])

    # "first N seconds/minutes"
    first_match = re.search(r"first\s+(\d+(?:\.\d+)?)\s*(s(?:ec(?:ond)?s?)?|m(?:in(?:ute)?s?)?)", text_lower)
    if first_match:
        val = float(first_match.group(1))
        unit = first_match.group(2)
        dur_secs = val * 60 if unit.startswith("m") else val
        return TimeRange(0.0, dur_secs)

    # "minute N" (single minute slot)
    min_n = re.search(r"minute\s+(\d+)", text_lower)
    if min_n:
        n = int(min_n.group(1))
        return TimeRange(float((n - 1) * 60), float(n * 60))

    # "around N sec/min"
    around_match = re.search(
        r"around\s+([\d:\.]+\s*(?:s(?:ec(?:ond)?s?)?|m(?:in(?:ute)?s?)?)?)",
        text_lower,
    )
    if around_match:
        t = parse_time_token(around_match.group(1).strip())
        if t is not None:
            return TimeRange(max(0.0, t - 15), t + 15)

    # Range patterns: "X to Y", "X - Y", "from X to Y", "between X and Y"
    range_patterns = [
        r"from\s+(.+?)\s+to\s+(.+?)(?:\s|$|[,\.?!])",
        r"between\s+(.+?)\s+and\s+(.+?)(?:\s|$|[,\.?!])",
        r"(.+?)\s+to\s+(.+?)(?:\s|$|[,\.?!])",
        r"(.+?)\s*[-–]\s*(.+?)(?:\s|$|[,\.?!])",
        r"(.+?)\s+through\s+(.+?)(?:\s|$|[,\.?!])",
    ]

    for pattern in range_patterns:
        m = re.search(pattern, text_lower)
        if m:
            start_token = m.group(1).strip()
            end_token = m.group(2).strip()
            start = parse_time_token(start_token)
            end = parse_time_token(end_token)
            if start is not None and end is not None and end > start:
                return TimeRange(start, end)

    return None


def format_time(seconds: float) -> str:
    """Format seconds as M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"
