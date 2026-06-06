"""Lumen chat â€” rate-limited, authenticated, IDOR-safe, budget-guarded."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Video, TranscriptSegment, Scene, Notes
from ..schemas import ChatRequest, ChatResponse, SourceChip
from ..auth import get_current_user, AuthUser
from ..limiter import limiter
from ..budget import check_budget
from ..config import get_settings
from ..security import get_owned_video, validate_message_length
from ..providers import get_provider
from ..pipeline.embeddings import search_index, search_time_range
from ..utils.time_parser import parse_time_range, format_time

router = APIRouter(prefix="/videos", tags=["lumen"])
settings = get_settings()

QUICK_SUGGESTIONS = [
    "Summarize the intro",
    "What are the main topics?",
    "What happened in the last 30 seconds?",
    "What is shown visually?",
]


@router.post("/{video_id}/chat", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().RATELIMIT_CHAT)
def lumen_chat(
    request: Request,
    body: ChatRequest,
    video: Video = Depends(get_owned_video),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Lumen: answer questions about the video, grounded in its content only."""
    validate_message_length(body.message, settings.LUMEN_MAX_MSG_LEN)

    # Budget guard before hitting the LLM
    check_budget(settings.REDIS_URL, settings.MAX_AI_CALLS_PER_DAY)

    notes = db.query(Notes).filter(Notes.video_id == video.id).first()
    if not notes:
        raise HTTPException(404, "Video not processed yet")

    provider = get_provider()
    message = body.message.strip()
    history = [m.dict() for m in body.history]

    time_range = parse_time_range(message, video.duration)
    context_segments = []
    seek_to = None

    if time_range:
        segments = db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video.id).all()
        scenes = db.query(Scene).filter(Scene.video_id == video.id).all()
        segs_data = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        scenes_data = [
            {
                "start_time": s.start_time,
                "end_time": s.end_time,
                "description": s.description,
                "scene_label": s.scene_label,
                "scene_number": s.scene_number,
            }
            for s in scenes
        ]
        context_segments = search_time_range(time_range.start, time_range.end, segs_data, scenes_data)
        seek_to = time_range.start

    elif notes.faiss_index_path:
        context_segments = search_index(
            message,
            notes.faiss_index_path,
            notes.faiss_metadata_path,
            provider,
            top_k=settings.FAISS_TOP_K,
        )
        if context_segments:
            seek_to = context_segments[0].get("start")
    else:
        # FAISS unavailable — fall back to keyword search over transcript for context
        all_segments = db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video.id).all()
        msg_lower = message.lower()
        for seg in all_segments:
            if any(word in seg.text.lower() for word in msg_lower.split() if len(word) > 3):
                context_segments.append({"type": "transcript", "start": seg.start, "end": seg.end, "text": seg.text})
                if seek_to is None:
                    seek_to = seg.start
        context_segments = context_segments[:settings.FAISS_TOP_K]

    answer = provider.answer_question(
        question=message,
        context_segments=context_segments,
        history=history,
        video_title=notes.title or video.filename or "",
    )

    sources = []
    seen: set[tuple[float, float]] = set()
    for seg in context_segments[:5]:
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        key = (round(start, 1), round(end, 1))
        if key not in seen:
            seen.add(key)
            label = seg.get("label") or ("Transcript" if seg.get("type") == "transcript" else "Visual")
            sources.append(SourceChip(
                label=f”{label} ({format_time(start)}–{format_time(end)})”,
                start=start,
                end=end,
            ))

    return ChatResponse(answer=answer, sources=sources, seek_to=seek_to)


@router.get("/{video_id}/chat/suggestions")
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def get_suggestions(
    request: Request,
    video: Video = Depends(get_owned_video),
):
    return {"suggestions": QUICK_SUGGESTIONS}


