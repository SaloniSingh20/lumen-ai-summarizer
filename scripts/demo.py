#!/usr/bin/env python3
"""
make demo — runs the full pipeline on the sample video and prints the JSON notes.
Requires: backend dependencies installed, Redis running, API_PROVIDER set in .env
"""
import sys
import os
import time
import json
import subprocess
import tempfile
import shutil

# Point to backend dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLE_VIDEO = os.path.join(os.path.dirname(__file__), "..", "samples", "sample.mp4")
API_URL = "http://localhost:8000"


def wait_for_api(timeout=30):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{API_URL}/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def demo_via_api():
    """Submit the sample video to the running API and poll until done."""
    import urllib.request
    import urllib.parse

    print(f"\n{'='*60}")
    print("AI Video Summarizer — End-to-End Demo")
    print(f"{'='*60}\n")

    if not os.path.exists(SAMPLE_VIDEO):
        print(f"[ERROR] Sample video not found at: {SAMPLE_VIDEO}")
        print("Run: python scripts/create_sample.py")
        sys.exit(1)

    print(f"[1/4] Checking API at {API_URL}...")
    if not wait_for_api():
        print("[ERROR] API not reachable. Start it first: uvicorn app.main:app (from backend/)")
        sys.exit(1)
    print("      API is up.")

    print(f"\n[2/4] Uploading sample video: {os.path.basename(SAMPLE_VIDEO)}")
    import http.client
    import mimetypes
    import uuid

    boundary = uuid.uuid4().hex
    with open(SAMPLE_VIDEO, "rb") as f:
        video_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="sample.mp4"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode() + video_data + f"\r\n--{boundary}--\r\n".encode()

    conn = http.client.HTTPConnection("localhost", 8000)
    conn.request(
        "POST", "/jobs/upload",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = conn.getresponse()
    data = json.loads(resp.read())
    job_id = data["job_id"]
    video_id = data["video_id"]
    print(f"      Job ID: {job_id}")
    print(f"      Video ID: {video_id}")

    print("\n[3/4] Processing (polling every 2s)...")
    while True:
        conn = http.client.HTTPConnection("localhost", 8000)
        conn.request("GET", f"/jobs/{job_id}")
        resp = conn.getresponse()
        job = json.loads(resp.read())
        print(f"      [{job['progress']:5.1f}%] {job['stage']}")
        if job["status"] == "completed":
            break
        if job["status"] == "failed":
            print(f"\n[ERROR] Job failed: {job.get('error', 'Unknown error')}")
            sys.exit(1)
        time.sleep(2)

    print("\n[4/4] Fetching results...")
    conn = http.client.HTTPConnection("localhost", 8000)
    conn.request("GET", f"/videos/{video_id}")
    resp = conn.getresponse()
    video = json.loads(resp.read())
    notes = video.get("notes", {})

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(json.dumps(notes, indent=2, ensure_ascii=False))

    print(f"\n{'='*60}")
    print(f"Demo complete!")
    print(f"  Video ID:  {video_id}")
    print(f"  Title:     {notes.get('title', 'N/A')}")
    print(f"  TL;DR:     {notes.get('tldr', 'N/A')[:100]}...")
    print(f"  Topics:    {', '.join(notes.get('main_topics', []))}")
    print(f"  Scenes:    {len(video.get('scenes', []))}")
    print(f"  Segments:  {len(video.get('transcript_segments', []))}")
    print(f"\n  View at:   http://localhost:3000/results/{video_id}")
    print(f"{'='*60}\n")


def demo_direct():
    """Run the pipeline directly without a running API (for CI/testing)."""
    print("Running pipeline directly (no API needed)...")
    os.environ.setdefault("AI_PROVIDER", "api")

    # Set up paths
    os.makedirs("backend/uploads/demo", exist_ok=True)
    os.makedirs("backend/keyframes/demo", exist_ok=True)
    os.makedirs("backend/data", exist_ok=True)

    dest = "backend/uploads/demo/sample.mp4"
    shutil.copy(SAMPLE_VIDEO, dest)

    # Import and run pipeline
    sys.path.insert(0, "backend")
    from app.database import init_db, SessionLocal
    from app.models import Job, Video
    from app.pipeline.runner import run_pipeline
    import uuid

    init_db()
    db = SessionLocal()

    job_id = str(uuid.uuid4())
    video_id = str(uuid.uuid4())

    job = Job(id=job_id, status="pending", stage="Queued", progress=0.0)
    db.add(job)
    db.flush()

    video = Video(id=video_id, job_id=job_id, filename="sample.mp4", file_path=dest)
    db.add(video)
    db.commit()

    print("Running pipeline...")
    run_pipeline(job_id, video_id, db)

    from app.models import Notes
    notes = db.query(Notes).filter(Notes.video_id == video_id).first()
    if notes:
        notes_dict = {
            "title": notes.title,
            "tldr": notes.tldr,
            "main_topics": notes.main_topics,
            "key_concepts": notes.key_concepts,
            "detailed_notes": notes.detailed_notes,
            "key_takeaways": notes.key_takeaways,
            "visual_summary": notes.visual_summary,
            "confidence_notes": notes.confidence_notes,
        }
        print("\n=== NOTES JSON ===")
        print(json.dumps(notes_dict, indent=2, ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "api"
    if mode == "direct":
        demo_direct()
    else:
        demo_via_api()
