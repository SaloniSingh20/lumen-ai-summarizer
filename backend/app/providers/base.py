from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    language: Optional[str] = None


class AIProvider(ABC):
    """Abstract interface for all AI operations. The rest of the app NEVER calls a model directly."""

    @abstractmethod
    def transcribe(self, audio_path: str) -> tuple[List[TranscriptSegment], str]:
        """
        Transcribe audio file.
        Returns (segments, detected_language).
        """
        ...

    @abstractmethod
    def describe_frame(self, image_path: str) -> str:
        """
        Describe what is literally visible in an image frame.
        Must not hallucinate or speculate.
        """
        ...

    @abstractmethod
    def generate_notes(
        self,
        transcript_segments: List[TranscriptSegment],
        visual_descriptions: List[dict],
        has_audio: bool,
        language: str = "en",
    ) -> dict:
        """
        Generate structured notes JSON from transcript + visual descriptions.
        Returns dict matching the OutputSchema.
        """
        ...

    @abstractmethod
    def answer_question(
        self,
        question: str,
        context_segments: List[dict],
        history: List[dict],
        video_title: str = "",
    ) -> str:
        """
        Answer a question grounded only in provided context segments.
        Used by Lumen Q&A.
        """
        ...

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Embed texts into float32 vectors. Shape: (len(texts), dim).
        Always uses sentence-transformers locally regardless of provider.
        """
        ...
