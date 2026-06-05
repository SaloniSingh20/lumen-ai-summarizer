"""
Groq provider — free tier, no credit card needed.

LLM:  llama-3.3-70b-versatile  (fast, high quality, free)
VLM:  llama-3.2-11b-vision-preview (free vision model)
Embeddings: sentence-transformers locally (always free)

Free tier limits (as of 2026): ~14,400 req/day, 6,000 tokens/min
Plenty for personal video summarization.
Sign up: https://console.groq.com
"""
import base64
import json
import re
from typing import List
import numpy as np

from .base import AIProvider, TranscriptSegment
from .prompts import FRAME_DESCRIPTION_PROMPT, NOTES_GENERATION_PROMPT, LUMEN_SYSTEM_PROMPT, LUMEN_USER_PROMPT
from .embedder import embed_texts
from .local_provider import (
    _build_content_block, _format_context, _format_history,
    _parse_json_response, _strip_banned,
)
from ..config import get_settings

settings = get_settings()

_LLM_MODEL    = "llama-3.3-70b-versatile"
# Vision models in order of preference — falls back if one is decommissioned
_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",  # Llama 4 Scout (vision + text)
    "llama-3.2-90b-vision-preview",               # Llama 3.2 90B vision
    "llama-3.2-11b-vision-preview",               # Llama 3.2 11B vision (older)
]


class GroqProvider(AIProvider):
    def __init__(self):
        from groq import Groq
        self._client = Groq(api_key=settings.GROQ_API_KEY)

    # ── Transcription: Groq Whisper API (no local PyTorch model needed) ─────
    def transcribe(self, audio_path: str) -> tuple[List[TranscriptSegment], str]:
        import os
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        result = self._client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), audio_bytes),
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
        language = getattr(result, "language", None) or "en"
        raw_segments = getattr(result, "segments", None) or []
        segments = [
            TranscriptSegment(
                start=float(getattr(seg, "start", 0)),
                end=float(getattr(seg, "end", 0)),
                text=getattr(seg, "text", "").strip(),
                language=language,
            )
            for seg in raw_segments
            if getattr(seg, "text", "").strip()
        ]
        return segments, language

    # ── VLM: llama-3.2-vision via Groq ─────────────────────────────────────
    def describe_frame(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        last_err = None
        for vision_model in _VISION_MODELS:
            try:
                response = self._client.chat.completions.create(
                    model=vision_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": FRAME_DESCRIPTION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                            },
                        ],
                    }],
                    temperature=0.1,
                    max_tokens=350,
                )
                raw = response.choices[0].message.content or ""
                return _strip_banned(raw.strip())
            except Exception as e:
                last_err = e
                import logging
                logging.getLogger(__name__).warning(f"Vision model {vision_model} failed: {e}, trying next")
                continue

        # All vision models failed — return a safe fallback
        import logging
        logging.getLogger(__name__).error(f"All vision models failed: {last_err}")
        return "Visual content present but description unavailable."

    # ── Notes generation: llama-3.3-70b ────────────────────────────────────
    def generate_notes(
        self,
        transcript_segments: List[TranscriptSegment],
        visual_descriptions: List[dict],
        has_audio: bool,
        language: str = "en",
    ) -> dict:
        content_block = _build_content_block(transcript_segments, visual_descriptions, has_audio)
        prompt = NOTES_GENERATION_PROMPT.format(
            content_block=content_block, has_audio=str(has_audio).lower()
        )
        response = self._client.chat.completions.create(
            model=_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return _parse_json_response(raw)

    # ── Lumen Q&A ───────────────────────────────────────────────────────────
    def answer_question(
        self,
        question: str,
        context_segments: List[dict],
        history: List[dict],
        video_title: str = "",
    ) -> str:
        context      = _format_context(context_segments)
        history_text = _format_history(history)
        system       = LUMEN_SYSTEM_PROMPT.format(video_title=video_title)
        user_msg     = LUMEN_USER_PROMPT.format(
            context=context, history=history_text, question=question
        )
        response = self._client.chat.completions.create(
            model=_LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        return (response.choices[0].message.content or "").strip()

    # ── Embeddings: always local ────────────────────────────────────────────
    def embed(self, texts: List[str]) -> np.ndarray:
        return embed_texts(texts, settings.EMBEDDING_MODEL)
