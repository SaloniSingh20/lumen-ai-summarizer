"""Main pipeline runner — orchestrates all stages with progress updates."""
import os
import logging
from typing import Callable, Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import set_rls_context
from ..models import Job, Video, TranscriptSegment as TSModel, Scene as SceneModel, Notes
from ..providers import get_provider
from .ingest import probe_video
from .audio import extract_audio, detect_audio_presence
from .scenes import detect_scenes, extract_keyframe, deduplicate_descriptions
from .embeddings import build_faiss_index

logger = logging.getLogger(__name__)
settings = get_settings()

STAGES = [
    (0,   5,  "Probing video"),
    (5,   15, "Extracting audio"),
    (15,  20, "Detecting audio"),
    (20,  40, "Transcribing"),
    (40,  50, "Detecting scenes"),
    (50,  60, "Extracting keyframes"),
    (60,  80, "Analyzing visuals"),
    (80,  90, "Generating notes"),
    (90,  97, "Building search index"),
    (97, 100, "Finalizing"),
]


def run_transcript_only_pipeline(job_id: str, video_id: str, db: Session, partial: bool = False):
    """
    Lightweight pipeline for YouTube videos where yt-dlp download failed.
    Transcript segments are already in the DB; this stage just generates notes.

    `partial=True` means the "transcript" segments are actually synthesized
    from video metadata (title/description/chapters or scraped page tags)
    because no real captions were reachable — a notice is appended to
    confidence_notes so the user knows the summary is best-effort.
    """
    provider = get_provider()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        set_rls_context(db, video.owner_id)

        update_job(db, job_id, "Loading transcript", 20)
        segments = db.query(TSModel).filter(TSModel.video_id == video_id).order_by(TSModel.start).all()
        transcript_segments_data = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        detected_language = video.language_detected or "en"

        if not transcript_segments_data:
            raise ValueError("No transcript segments — cannot generate notes")

        update_job(db, job_id, "Generating notes", 60)
        from ..providers.base import TranscriptSegment as TSObj
        ts_objs = [TSObj(start=s["start"], end=s["end"], text=s["text"]) for s in transcript_segments_data]
        notes_data = provider.generate_notes(ts_objs, [], has_audio=True, language=detected_language)

        confidence_notes = notes_data.get("confidence_notes")
        if partial:
            notice = (
                "⚠️ Limited data: YouTube blocked full transcript/caption access for this video "
                "from our server, so this summary is generated from the video's title, description, "
                "and chapter list only — not the full spoken content. For a complete analysis, use "
                "the 'Upload File' option to upload the video directly."
            )
            confidence_notes = f"{notice}\n\n{confidence_notes}" if confidence_notes else notice

        notes = Notes(
            video_id=video_id,
            content_type=notes_data.get("content_type"),
            language_detected=notes_data.get("language_detected", detected_language),
            has_audio=True,
            title=notes_data.get("title"),
            tldr=notes_data.get("tldr"),
            main_topics=notes_data.get("main_topics", []),
            key_concepts=notes_data.get("key_concepts", []),
            detailed_notes=notes_data.get("detailed_notes"),
            key_takeaways=notes_data.get("key_takeaways", []),
            visual_summary=notes_data.get("visual_summary"),
            scenes_summary=notes_data.get("scenes", []),
            confidence_notes=confidence_notes,
        )
        db.add(notes)
        db.commit()

        update_job(db, job_id, "Complete", 100)
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "completed"
            job.progress = 100.0
            job.stage = "Complete"
            db.commit()

        from ..cache import invalidate_video
        invalidate_video(video_id)
        logger.info(f"Transcript-only pipeline completed for video {video_id}")

    except Exception as e:
        logger.exception(f"Transcript-only pipeline failed for job {job_id}: {e}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            db.commit()
        raise


def update_job(db: Session, job_id: str, stage: str, progress: float):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.stage = stage
        job.progress = round(progress, 1)
        job.status = "processing"
        db.commit()


def run_pipeline(job_id: str, video_id: str, db: Session):
    """Run the full processing pipeline for a video."""
    provider = get_provider()

    try:
        # Fetch video first (no RLS context yet — initial lookup by PK is safe)
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # Activate RLS context so all subsequent writes are owner-scoped
        set_rls_context(db, video.owner_id)

        file_path = video.file_path
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        upload_dir = os.path.dirname(file_path)
        keyframes_dir = os.path.join(settings.KEYFRAMES_DIR, video_id)
        faiss_dir = os.path.join(upload_dir, "faiss")

        # --- Stage 1: Probe ---
        update_job(db, job_id, "Probing video", 3)
        probe = probe_video(file_path)
        video.duration = probe["duration"]
        db.commit()

        # --- Stage 2: Extract audio ---
        update_job(db, job_id, "Extracting audio", 10)
        wav_path = ""
        if probe["has_audio_stream"]:
            wav_path = extract_audio(file_path, upload_dir)

        # --- Stage 3: Detect audio presence ---
        update_job(db, job_id, "Detecting audio", 18)
        has_audio = detect_audio_presence(wav_path) if wav_path else False
        video.has_audio = has_audio
        db.commit()

        # --- Stage 4: Transcribe ---
        transcript_segments_data = []
        detected_language = "en"
        if has_audio and wav_path:
            update_job(db, job_id, "Transcribing audio", 25)
            segments, detected_language = provider.transcribe(wav_path)
            video.language_detected = detected_language
            db.commit()

            for seg in segments:
                ts = TSModel(
                    video_id=video_id,
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                )
                db.add(ts)
            db.commit()

            transcript_segments_data = [
                {"start": s.start, "end": s.end, "text": s.text}
                for s in segments
            ]
        else:
            logger.info(f"No audio in {video_id}, skipping transcription.")

        # --- Stage 5: Scene detection ---
        update_job(db, job_id, "Detecting scenes", 45)
        scenes = detect_scenes(file_path, max_scenes=settings.MAX_SCENES)

        # --- Stage 6: Keyframe extraction ---
        update_job(db, job_id, "Extracting keyframes", 55)
        os.makedirs(keyframes_dir, exist_ok=True)
        for scene in scenes:
            kf_path = extract_keyframe(file_path, scene, keyframes_dir)
            scene["keyframe_path"] = kf_path

        # --- Stage 7: Visual understanding ---
        update_job(db, job_id, "Analyzing visuals", 62)
        raw_descriptions = []
        for i, scene in enumerate(scenes):
            kf_path = scene.get("keyframe_path", "")
            if kf_path and os.path.exists(kf_path):
                desc = provider.describe_frame(kf_path)
            else:
                desc = "No keyframe available for this scene."
            raw_descriptions.append(desc)
            progress = 62 + (i / max(len(scenes), 1)) * 16
            update_job(db, job_id, f"Analyzing scene {i+1}/{len(scenes)}", progress)

        # Deduplicate
        deduped_descriptions = deduplicate_descriptions(raw_descriptions)

        # Assign labels (will be enriched by notes generation)
        scenes_with_desc = []
        for i, (scene, desc) in enumerate(zip(scenes, deduped_descriptions)):
            scene_label = f"Scene {scene['scene_number']}"
            scenes_with_desc.append({
                **scene,
                "description": desc,
                "scene_label": scene_label,
            })

            sc = SceneModel(
                video_id=video_id,
                scene_number=scene["scene_number"],
                start_time=scene["start_time"],
                end_time=scene["end_time"],
                keyframe_path=scene.get("keyframe_path", ""),
                description=desc,
                scene_label=scene_label,
            )
            db.add(sc)
        db.commit()

        # --- Stage 8: Generate notes ---
        update_job(db, job_id, "Generating notes", 82)
        from ..providers.base import TranscriptSegment as TSObj
        ts_objs = [TSObj(start=s["start"], end=s["end"], text=s["text"]) for s in transcript_segments_data]
        notes_data = provider.generate_notes(ts_objs, scenes_with_desc, has_audio, detected_language)

        # Update scene labels from notes if provided
        notes_scenes = notes_data.get("scenes", [])
        db_scenes = db.query(SceneModel).filter(SceneModel.video_id == video_id).all()
        for i, db_scene in enumerate(db_scenes):
            if i < len(notes_scenes):
                ns = notes_scenes[i]
                db_scene.scene_label = ns.get("scene_label", db_scene.scene_label)
                db_scene.description = ns.get("description", db_scene.description)
        db.commit()

        notes = Notes(
            video_id=video_id,
            content_type=notes_data.get("content_type"),
            language_detected=notes_data.get("language_detected", detected_language),
            has_audio=has_audio,
            title=notes_data.get("title"),
            tldr=notes_data.get("tldr"),
            main_topics=notes_data.get("main_topics", []),
            key_concepts=notes_data.get("key_concepts", []),
            detailed_notes=notes_data.get("detailed_notes"),
            key_takeaways=notes_data.get("key_takeaways", []),
            visual_summary=notes_data.get("visual_summary"),
            scenes_summary=notes_data.get("scenes", []),
            confidence_notes=notes_data.get("confidence_notes"),
        )
        db.add(notes)
        db.commit()

        # --- Stage 9: Build FAISS index (skipped when ENABLE_FAISS=False) ---
        update_job(db, job_id, "Building search index", 92)
        if settings.ENABLE_FAISS:
            db_scenes_data = [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "description": s.description,
                    "scene_label": s.scene_label,
                    "scene_number": s.scene_number,
                }
                for s in db_scenes
            ]
            try:
                index_path, meta_path = build_faiss_index(
                    transcript_segments_data,
                    db_scenes_data,
                    provider,
                    faiss_dir,
                    video_id,
                )
                notes.faiss_index_path = index_path
                notes.faiss_metadata_path = meta_path
                db.commit()
            except Exception as emb_err:
                logger.warning(f"FAISS index skipped (memory/model error): {emb_err}")
        else:
            logger.info("FAISS index disabled (ENABLE_FAISS=False)")

        # --- Stage 10: Finalize ---
        update_job(db, job_id, "Complete", 100)
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "completed"
            job.progress = 100.0
            job.stage = "Complete"
            db.commit()

        # Bust any stale cache entries so the next GET sees fresh results
        from ..cache import invalidate_video
        invalidate_video(video_id)

        logger.info(f"Pipeline completed for video {video_id}")

    except Exception as e:
        logger.exception(f"Pipeline failed for job {job_id}: {e}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            db.commit()
        raise
