"""Compute analytics from transcript and notes data."""
import re
from collections import Counter
from typing import List, Optional

STOPWORDS = {
    "the", "a", "an", "is", "it", "in", "on", "of", "to", "and", "or", "but",
    "for", "with", "as", "at", "by", "that", "this", "was", "are", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "can", "not", "no", "so", "if", "i", "you", "he", "she",
    "we", "they", "its", "their", "his", "her", "my", "your", "our", "from",
    "into", "about", "up", "out", "there", "what", "which", "who", "how",
    "all", "also", "just", "more", "one", "two", "than", "then", "when",
    "where", "while", "very", "some", "been", "such", "even", "any", "each",
}


def compute_word_frequency(transcript_text: str, top_n: int = 20) -> List[dict]:
    words = re.findall(r"\b[a-zA-Z]{3,}\b", transcript_text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    counter = Counter(filtered)
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n)]


def compute_analytics(
    transcript_segments: List[dict],
    scenes: List[dict],
    duration: Optional[float],
    has_audio: bool,
    main_topics: Optional[List[str]] = None,
) -> dict:
    transcript_text = " ".join(s.get("text", "") for s in transcript_segments)
    total_words = len(transcript_text.split()) if transcript_text.strip() else 0

    word_frequency = compute_word_frequency(transcript_text) if transcript_text.strip() else []
    top_topics = main_topics or []

    words_per_minute = None
    speaking_ratio = None

    if has_audio and duration and duration > 0 and total_words > 0:
        words_per_minute = round((total_words / duration) * 60, 1)

        # Speaking time = sum of segment durations
        speaking_time = sum(
            max(0, s.get("end", 0) - s.get("start", 0))
            for s in transcript_segments
        )
        speaking_ratio = round(min(1.0, speaking_time / duration), 3)

    return {
        "word_frequency": word_frequency,
        "top_topics": top_topics,
        "scene_count": len(scenes),
        "duration": duration,
        "words_per_minute": words_per_minute,
        "speaking_ratio": speaking_ratio,
        "total_words": total_words,
    }
