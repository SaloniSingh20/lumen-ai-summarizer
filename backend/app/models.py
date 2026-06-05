from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import uuid


def gen_uuid():
    return str(uuid.uuid4())


class UserToken(Base):
    """
    Represents an authenticated user/session.
    - `id` is the stable owner identity stored on every user-data row.
    - `token` is the secret API key the client presents.
    Separating them lets us rotate keys without re-labelling owned rows.
    """
    __tablename__ = "user_tokens"

    id = Column(String, primary_key=True, default=gen_uuid)
    token = Column(String, unique=True, index=True, nullable=False, default=gen_uuid)
    name = Column(String, default="default")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="owner", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("user_tokens.id"), nullable=False, index=True)
    status = Column(String, default="pending")  # pending|processing|completed|failed
    stage = Column(String, default="")
    progress = Column(Float, default=0.0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("UserToken", back_populates="jobs")
    video = relationship("Video", back_populates="job", uselist=False)


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True, default=gen_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), unique=True)
    owner_id = Column(String, ForeignKey("user_tokens.id"), nullable=False, index=True)
    filename = Column(String)
    original_url = Column(String, nullable=True)
    file_path = Column(String)
    duration = Column(Float, nullable=True)
    has_audio = Column(Boolean, default=True)
    language_detected = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("UserToken", back_populates="videos")
    job = relationship("Job", back_populates="video")
    transcript_segments = relationship("TranscriptSegment", back_populates="video", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="video", cascade="all, delete-orphan")
    notes = relationship("Notes", back_populates="video", uselist=False, cascade="all, delete-orphan")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, ForeignKey("videos.id"))
    start = Column(Float)
    end = Column(Float)
    text = Column(Text)
    embedding_id = Column(Integer, nullable=True)

    video = relationship("Video", back_populates="transcript_segments")


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, ForeignKey("videos.id"))
    scene_number = Column(Integer)
    start_time = Column(Float)
    end_time = Column(Float)
    keyframe_path = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    scene_label = Column(String, nullable=True)
    embedding_id = Column(Integer, nullable=True)

    video = relationship("Video", back_populates="scenes")


class Notes(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, ForeignKey("videos.id"), unique=True)
    content_type = Column(String, nullable=True)
    language_detected = Column(String, nullable=True)
    has_audio = Column(Boolean, default=True)
    title = Column(String, nullable=True)
    tldr = Column(Text, nullable=True)
    main_topics = Column(JSON, nullable=True)
    key_concepts = Column(JSON, nullable=True)
    detailed_notes = Column(Text, nullable=True)
    key_takeaways = Column(JSON, nullable=True)
    visual_summary = Column(Text, nullable=True)
    scenes_summary = Column(JSON, nullable=True)
    confidence_notes = Column(Text, nullable=True)
    faiss_index_path = Column(String, nullable=True)
    faiss_metadata_path = Column(String, nullable=True)

    video = relationship("Video", back_populates="notes")
