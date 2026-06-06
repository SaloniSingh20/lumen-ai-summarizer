"""
Mock AI provider for CI / unit tests.

Returns stub data without importing any external AI package.
Use AI_PROVIDER=mock in CI so tests never hit google-generativeai or groq.
"""
from typing import List

import numpy as np

from .base import AIProvider, TranscriptSegment


class MockProvider(AIProvider):
    def transcribe(self, audio_path: str):
        return [], "en"

    def describe_frame(self, image_path: str) -> str:
        return "Mock scene description."

    def generate_notes(
        self,
        transcript_segments: List[TranscriptSegment],
        visual_descriptions: List[dict],
        has_audio: bool,
        language: str = "en",
    ) -> dict:
        return {
            "content_type": "video",
            "language_detected": language,
            "title": "Mock Title",
            "tldr": "Mock summary.",
            "main_topics": ["topic1", "topic2"],
            "key_concepts": [],
            "detailed_notes": "Mock notes.",
            "key_takeaways": ["takeaway1"],
            "visual_summary": "Mock visual summary.",
            "scenes": [],
            "confidence_notes": None,
        }

    def answer_question(
        self,
        question: str,
        context_segments: List[dict],
        history: List[dict],
        video_title: str = "",
    ) -> str:
        return "Mock answer."

    def embed(self, texts: List[str]) -> np.ndarray:
        dim = 384
        return np.zeros((len(texts), dim), dtype=np.float32)
