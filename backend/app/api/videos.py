"""
Video results, search, analytics, PDF export, and protected media streaming.

Every endpoint uses get_owned_video / get_owned_job so that:
  - Unauthenticated requests â†’ 401
  - Wrong-owner requests    â†’ 404 (not 403; don't reveal existence)
  - Public static mounts are REMOVED; files served only here, after auth.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Video, TranscriptSegment, Scene, Notes
from ..schemas import VideoOut, SearchResponse, SearchResult, AnalyticsOut
from ..utils.pdf_export import generate_pdf
from ..utils.analytics import compute_analytics
from ..pipeline.embeddings import search_index
from ..providers import get_provider
from ..config import get_settings
from ..auth import get_current_user, AuthUser
from ..limiter import limiter
from ..security import get_owned_video, generate_media_token, verify_media_token
from .. import cache

router = APIRouter(prefix="/videos", tags=["videos"])
settings = get_settings()


@router.get("", response_model=list[VideoOut])
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def list_videos(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """List all videos for the current user (newest first) — powers the dashboard."""
    from ..database import set_rls_context
    set_rls_context(db, current_user.id)
    videos = (
        db.query(Video)
        .filter(Video.owner_id == current_user.id)
        .order_by(Video.created_at.desc())
        .limit(50)
        .all()
    )
    return videos


@router.get("/{video_id}", response_model=VideoOut)
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def get_video(
    request: Request,
    video: Video = Depends(get_owned_video),
    db: Session = Depends(get_db),
):
    # Serve from cache when available (avoids N+1 DB joins on repeated requests)
    cached = cache.get_video(video.id)
    if cached:
        return cached
    # Cache miss â€” build response and store it
    # Trigger lazy loading of relationships before returning
    _ = video.transcript_segments, video.scenes, video.notes
    db.refresh(video)
    return video


@router.get("/{video_id}/search", response_model=SearchResponse)
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def search_video(
    request: Request,
    q: str = Query(..., min_length=1, max_length=300),
    video: Video = Depends(get_owned_video),
    db: Session = Depends(get_db),
):
    """Semantic search over transcript + scenes for this video."""
    # Cache by query so identical searches skip FAISS entirely
    cached_results = cache.get_search(video.id, q)
    if cached_results is not None:
        return SearchResponse(results=[SearchResult(**r) for r in cached_results])

    notes = db.query(Notes).filter(Notes.video_id == video.id).first()

    if notes and notes.faiss_index_path:
        raw_results = search_index(
            q,
            notes.faiss_index_path,
            notes.faiss_metadata_path,
            get_provider(),
            top_k=settings.FAISS_TOP_K,
        )
        results = [
            SearchResult(
                type=r["type"],
                text=r["text"],
                start=r["start"],
                end=r["end"],
                score=r["score"],
                label=r.get("label"),
            )
            for r in raw_results
        ]
    else:
        # FAISS unavailable (disabled or not built yet) — fall back to substring search
        segments = db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video.id).all()
        scenes = db.query(Scene).filter(Scene.video_id == video.id).all()
        q_lower = q.lower()
        results = []
        for seg in segments:
            if q_lower in seg.text.lower():
                results.append(SearchResult(
                    type="transcript", text=seg.text,
                    start=seg.start, end=seg.end, score=1.0,
                ))
        for sc in scenes:
            if sc.description and q_lower in sc.description.lower():
                results.append(SearchResult(
                    type="scene", text=sc.description,
                    start=sc.start_time, end=sc.end_time,
                    score=0.8, label=sc.scene_label,
                ))
        results = results[:settings.FAISS_TOP_K]

    # Store in cache for subsequent identical queries
    cache.set_search(video.id, q, [r.dict() for r in results])
    return SearchResponse(results=results)


@router.get("/{video_id}/analytics", response_model=AnalyticsOut)
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def get_analytics(
    request: Request,
    video: Video = Depends(get_owned_video),
    db: Session = Depends(get_db),
):
    cached = cache.get_analytics(video.id)
    if cached:
        return AnalyticsOut(**cached)

    segments = db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video.id).all()
    scenes = db.query(Scene).filter(Scene.video_id == video.id).all()
    notes = db.query(Notes).filter(Notes.video_id == video.id).first()

    segs_data = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    scenes_data = [{"start_time": s.start_time, "end_time": s.end_time} for s in scenes]
    main_topics = notes.main_topics if notes else []

    analytics = compute_analytics(segs_data, scenes_data, video.duration, video.has_audio, main_topics)
    cache.set_analytics(video.id, analytics)
    return AnalyticsOut(**analytics)


@router.get("/{video_id}/export/pdf")
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def export_pdf(
    request: Request,
    video: Video = Depends(get_owned_video),
    db: Session = Depends(get_db),
):
    notes = db.query(Notes).filter(Notes.video_id == video.id).first()
    if not notes:
        raise HTTPException(404, "Notes not ready yet")

    notes_dict = {
        "content_type": notes.content_type,
        "language_detected": notes.language_detected,
        "has_audio": notes.has_audio,
        "title": notes.title,
        "tldr": notes.tldr,
        "main_topics": notes.main_topics,
        "key_concepts": notes.key_concepts,
        "detailed_notes": notes.detailed_notes,
        "key_takeaways": notes.key_takeaways,
        "visual_summary": notes.visual_summary,
        "scenes": notes.scenes_summary,
        "confidence_notes": notes.confidence_notes,
    }
    pdf_bytes = generate_pdf(notes_dict, video.filename)
    safe_title = (notes.title or video.filename or "notes").replace("/", "_")[:50]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
    )


# ---------------------------------------------------------------------------
# Protected keyframe serving (ownership-checked; replaces /keyframes static mount)
# ---------------------------------------------------------------------------

@router.get("/{video_id}/keyframes/{scene_number}")
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def get_keyframe(
    request: Request,
    scene_number: int,
    video: Video = Depends(get_owned_video),
    db: Session = Depends(get_db),
):
    """Serve a keyframe image â€” only to the video's owner."""
    scene = (
        db.query(Scene)
        .filter(Scene.video_id == video.id, Scene.scene_number == scene_number)
        .first()
    )
    if not scene or not scene.keyframe_path:
        raise HTTPException(404, "Keyframe not found")
    if not os.path.exists(scene.keyframe_path):
        raise HTTPException(404, "Keyframe file missing")
    return FileResponse(scene.keyframe_path, media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Protected video streaming via short-lived signed tokens
# ---------------------------------------------------------------------------

@router.get("/{video_id}/media-token")
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def get_media_token(
    request: Request,
    video: Video = Depends(get_owned_video),
):
    """
    Issue a short-lived signed token (5 min) for video streaming.
    Returns 404 for caption-only videos (no file was downloaded).
    The browser <video> element cannot send Authorization headers, so we
    generate a signed URL token here and use it in the stream endpoint.
    """
    if not video.file_path:
        raise HTTPException(404, "No video file — this video was processed from captions only")
    token = generate_media_token(video.id, video.owner_id, settings.SECRET_KEY)
    return {"token": token, "ttl": 300}


@router.get("/{video_id}/stream")
def stream_video(
    video_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Stream the uploaded video file. Requires a signed media token from
    /media-token. No Bearer auth (the <video> element can't send it).
    """
    # Look up the video first (no owner filter yet â€” we verify via token)
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Not found")

    if not verify_media_token(token, video_id, video.owner_id, settings.SECRET_KEY):
        raise HTTPException(403, "Invalid or expired media token")

    if not video.file_path or not os.path.exists(video.file_path):
        raise HTTPException(404, "Video file not found")

    return FileResponse(
        video.file_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )

