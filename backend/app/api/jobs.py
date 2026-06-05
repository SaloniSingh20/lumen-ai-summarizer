"""Job management endpoints — rate-limited, authenticated, IDOR-safe."""
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, Video
from ..schemas import JobStatus, UploadResponse
from ..config import get_settings
from ..auth import get_current_user, AuthUser
from ..limiter import limiter
from ..budget import check_budget
from ..security import get_owned_job, validate_ingest_url, validate_upload_magic
from ..pipeline.ingest import download_url, get_filename_from_url

router = APIRouter(prefix="/jobs", tags=["jobs"])
settings = get_settings()


@router.post("/upload", response_model=UploadResponse)
@limiter.limit(lambda: get_settings().RATELIMIT_UPLOAD_HOURLY)
@limiter.limit(lambda: get_settings().RATELIMIT_UPLOAD)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Upload a video file and create a processing job."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    header = await file.read(12)
    await file.seek(0)
    validate_upload_magic(file.filename, header)

    check_budget(settings.REDIS_URL, settings.MAX_AI_CALLS_PER_DAY)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    video_id   = str(uuid.uuid4())
    upload_path = os.path.join(settings.UPLOAD_DIR, video_id)
    os.makedirs(upload_path, exist_ok=True)

    safe_name = os.path.basename(file.filename).replace("..", "").strip() or "video.mp4"
    file_path  = os.path.join(upload_path, safe_name)

    total_size = 0
    max_bytes  = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    with open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > max_bytes:
                os.remove(file_path)
                raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.")
            f.write(chunk)

    return _create_job_and_enqueue(db, video_id, file_path, safe_name, None, current_user.id)


@router.post("/url", response_model=UploadResponse)
@limiter.limit(lambda: get_settings().RATELIMIT_UPLOAD_HOURLY)
@limiter.limit(lambda: get_settings().RATELIMIT_UPLOAD)
async def submit_url(
    request: Request,
    url: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """Submit a YouTube/video URL for processing."""
    validate_ingest_url(url)
    check_budget(settings.REDIS_URL, settings.MAX_AI_CALLS_PER_DAY)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    video_id   = str(uuid.uuid4())
    upload_path = os.path.join(settings.UPLOAD_DIR, video_id)
    os.makedirs(upload_path, exist_ok=True)

    try:
        file_path = download_url(url, upload_path)
    except Exception as e:
        raise HTTPException(400, str(e))

    filename = get_filename_from_url(url)
    return _create_job_and_enqueue(db, video_id, file_path, filename, url, current_user.id)


@router.get("/{job_id}", response_model=JobStatus)
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def get_job(
    request: Request,
    job: Job = Depends(get_owned_job),
):
    return job


@router.get("", response_model=list[JobStatus])
@limiter.limit(lambda: get_settings().RATELIMIT_READ)
def list_jobs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """List all jobs for the current user (newest first)."""
    from ..database import set_rls_context
    set_rls_context(db, current_user.id)
    jobs = (
        db.query(Job)
        .filter(Job.owner_id == current_user.id)
        .order_by(Job.created_at.desc())
        .limit(50)
        .all()
    )
    return jobs


def _create_job_and_enqueue(
    db: Session,
    video_id: str,
    file_path: str,
    filename: str,
    original_url: str | None,
    owner_id: str,
) -> UploadResponse:
    from worker.tasks import process_video_task

    job = Job(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        status="pending",
        stage="Queued",
        progress=0.0,
    )
    db.add(job)
    db.flush()

    video = Video(
        id=video_id,
        job_id=job.id,
        owner_id=owner_id,
        filename=filename,
        file_path=file_path,
        original_url=original_url,
    )
    db.add(video)
    db.commit()

    process_video_task.delay(job.id, video_id)

    return UploadResponse(job_id=job.id, video_id=video_id, message="Job queued successfully")
