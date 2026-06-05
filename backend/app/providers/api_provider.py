"""API provider: Google Gemini (LLM+VLM) + faster-whisper local."""
import base64
import json
import re
from typing import List
import numpy as np

from .base import AIProvider, TranscriptSegment
from .prompts import FRAME_DESCRIPTION_PROMPT, NOTES_GENERATION_PROMPT, LUMEN_SYSTEM_PROMPT, LUMEN_USER_PROMPT
from .embedder import embed_texts
from .local_provider import _build_content_block, _format_context, _format_history, _parse_json_response, _strip_banned
from ..config import get_settings

settings = get_settings()


class APIProvider(AIProvider):
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self._genai = genai
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def transcribe(self, audio_path: str) -> tuple[List[TranscriptSegment], str]:
        if settings.USE_OPENAI_WHISPER and settings.OPENAI_API_KEY:
            return self._transcribe_openai(audio_path)
        return self._transcribe_local(audio_path)

    def _transcribe_local(self, audio_path: str) -> tuple[List[TranscriptSegment], str]:
        from faster_whisper import WhisperModel
        model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        segments_raw, info = model.transcribe(audio_path, language=None, beam_size=5)
        segments = [
            TranscriptSegment(start=s.start, end=s.end, text=s.text.strip(), language=info.language)
            for s in segments_raw
            if s.text.strip()
        ]
        return segments, info.language

    def _transcribe_openai(self, audio_path: str) -> tuple[List[TranscriptSegment], str]:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        segments = [
            TranscriptSegment(start=s["start"], end=s["end"], text=s["text"].strip())
            for s in result.segments
            if s["text"].strip()
        ]
        language = getattr(result, "language", "en")
        return segments, language

    def describe_frame(self, image_path: str) -> str:
        import PIL.Image
        img = PIL.Image.open(image_path)
        response = self._model.generate_content(
            [FRAME_DESCRIPTION_PROMPT, img],
            generation_config={"temperature": 0.1, "max_output_tokens": 300},
        )
        raw = response.text
        return _strip_banned(raw.strip())

    def generate_notes(
        self,
        transcript_segments: List[TranscriptSegment],
        visual_descriptions: List[dict],
        has_audio: bool,
        language: str = "en",
    ) -> dict:
        content_block = _build_content_block(transcript_segments, visual_descriptions, has_audio)
        prompt = NOTES_GENERATION_PROMPT.format(content_block=content_block, has_audio=str(has_audio).lower())
        response = self._model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 4096},
        )
        return _parse_json_response(response.text)

    def answer_question(
        self,
        question: str,
        context_segments: List[dict],
        history: List[dict],
        video_title: str = "",
    ) -> str:
        context = _format_context(context_segments)
        history_text = _format_history(history)
        system = LUMEN_SYSTEM_PROMPT.format(video_title=video_title)
        user_msg = LUMEN_USER_PROMPT.format(context=context, history=history_text, question=question)
        full_prompt = f"{system}\n\n{user_msg}"
        response = self._model.generate_content(
            full_prompt,
            generation_config={"temperature": 0.3, "max_output_tokens": 1024},
        )
        return response.text.strip()

    def embed(self, texts: List[str]) -> np.ndarray:
        return embed_texts(texts, settings.EMBEDDING_MODEL)
