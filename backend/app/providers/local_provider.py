"""Local provider: Ollama (LLM+VLM) + faster-whisper. No API keys needed."""
import base64
import json
import re
from typing import List
import numpy as np

from .base import AIProvider, TranscriptSegment
from .prompts import FRAME_DESCRIPTION_PROMPT, NOTES_GENERATION_PROMPT, LUMEN_SYSTEM_PROMPT, LUMEN_USER_PROMPT
from .embedder import embed_texts
from ..config import get_settings

settings = get_settings()

BANNED_COLOR_PHRASES = re.compile(
    r"\b(red hues|rgb|rgba|saturation|color values|color grading|hue shift|pixel[s]?|"
    r"color correction|contrast level|luminance|brightness level)\b",
    re.IGNORECASE,
)


def _strip_banned(text: str) -> str:
    return BANNED_COLOR_PHRASES.sub("[visual detail]", text)


class LocalProvider(AIProvider):
    def __init__(self):
        import ollama
        self._client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        self._llm_model = settings.OLLAMA_LLM_MODEL
        self._vlm_model = settings.OLLAMA_VLM_MODEL

    def transcribe(self, audio_path: str) -> tuple[List[TranscriptSegment], str]:
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

    def describe_frame(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        response = self._client.chat(
            model=self._vlm_model,
            messages=[{
                "role": "user",
                "content": FRAME_DESCRIPTION_PROMPT,
                "images": [img_b64],
            }],
        )
        raw = response["message"]["content"]
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
        response = self._client.chat(
            model=self._llm_model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2},
        )
        raw = response["message"]["content"]
        return _parse_json_response(raw)

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
        response = self._client.chat(
            model=self._llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            options={"temperature": 0.3},
        )
        return response["message"]["content"].strip()

    def embed(self, texts: List[str]) -> np.ndarray:
        return embed_texts(texts, settings.EMBEDDING_MODEL)


def _build_content_block(
    segments: List[TranscriptSegment],
    visual_descs: List[dict],
    has_audio: bool,
) -> str:
    parts = []
    if has_audio and segments:
        transcript_text = " ".join(s.text for s in segments)
        parts.append(f"=== TRANSCRIPT ===\n{transcript_text}")
    else:
        parts.append("=== TRANSCRIPT ===\n[No audio detected in this video]")

    if visual_descs:
        vis_lines = []
        for v in visual_descs:
            label = v.get("scene_label", f"Scene {v.get('scene_number', '?')}")
            desc = v.get("description", "")
            if desc:
                vis_lines.append(f"- {label}: {desc}")
        if vis_lines:
            parts.append("=== VISUAL DESCRIPTIONS ===\n" + "\n".join(vis_lines))

    return "\n\n".join(parts)


def _format_context(segments: List[dict]) -> str:
    lines = []
    for seg in segments:
        t = seg.get("type", "")
        text = seg.get("text", "")
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        label = seg.get("label", "")
        time_str = f"[{_fmt_time(start)} - {_fmt_time(end)}]"
        if t == "transcript":
            lines.append(f"TRANSCRIPT {time_str}: {text}")
        else:
            lines.append(f"VISUAL {time_str} ({label}): {text}")
    return "\n".join(lines) if lines else "No relevant content found."


def _format_history(history: List[dict]) -> str:
    if not history:
        return "(no prior conversation)"
    lines = []
    for msg in history[-6:]:
        role = msg.get("role", "user").capitalize()
        lines.append(f"{role}: {msg.get('content', '')}")
    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _parse_json_response(raw: str) -> dict:
    # Extract JSON from markdown code block if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON object
        match = re.search(r"\{[\s\S]+\}", raw)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return {"title": "Processing Error", "tldr": "Could not parse AI response.", "detailed_notes": raw}
