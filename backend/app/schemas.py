from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class JobCreate(BaseModel):
    pass


class JobStatus(BaseModel):
    id: str
    status: str
    stage: str
    progress: float
    error: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TranscriptSegmentOut(BaseModel):
    id: int
    start: float
    end: float
    text: str

    class Config:
        from_attributes = True


class SceneOut(BaseModel):
    id: int
    scene_number: int
    start_time: float
    end_time: float
    keyframe_path: Optional[str] = None
    description: Optional[str] = None
    scene_label: Optional[str] = None

    class Config:
        from_attributes = True


class KeyConcept(BaseModel):
    concept: str
    explanation: str


class NotesOut(BaseModel):
    content_type: Optional[str] = None
    language_detected: Optional[str] = None
    has_audio: bool = True
    title: Optional[str] = None
    tldr: Optional[str] = None
    main_topics: Optional[List[str]] = None
    key_concepts: Optional[List[KeyConcept]] = None
    detailed_notes: Optional[str] = None
    key_takeaways: Optional[List[str]] = None
    visual_summary: Optional[str] = None
    scenes: Optional[List[Any]] = None
    confidence_notes: Optional[str] = None

    class Config:
        from_attributes = True


class VideoOut(BaseModel):
    id: str
    job_id: str
    filename: str
    original_url: Optional[str] = None
    duration: Optional[float] = None
    has_audio: bool
    created_at: Optional[datetime] = None
    language_detected: Optional[str] = None
    transcript_segments: List[TranscriptSegmentOut] = []
    scenes: List[SceneOut] = []
    notes: Optional[NotesOut] = None

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    type: str  # "transcript" or "scene"
    text: str
    start: float
    end: float
    score: float
    label: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class SourceChip(BaseModel):
    label: str
    start: float
    end: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChip] = []
    seek_to: Optional[float] = None


class UploadResponse(BaseModel):
    job_id: str
    video_id: str
    message: str


class AnalyticsOut(BaseModel):
    word_frequency: List[dict]
    top_topics: List[str]
    scene_count: int
    duration: Optional[float]
    words_per_minute: Optional[float]
    speaking_ratio: Optional[float]
    total_words: int
