"""Stages 5+6: Scene detection with PySceneDetect + keyframe extraction with OpenCV."""
import os
import logging
from typing import List
import cv2

logger = logging.getLogger(__name__)


def _video_duration(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    return frames / fps if fps > 0 else 0


def _fallback_scenes(video_path: str) -> List[dict]:
    """Return evenly-spaced scenes when PySceneDetect finds none or fails."""
    duration = _video_duration(video_path)
    if duration <= 0:
        return [{"scene_number": 1, "start_time": 0.0, "end_time": 10.0}]

    # For short videos (<30s): 1 scene. Medium (30–120s): 2 scenes. Longer: 3.
    if duration < 30:
        n = 1
    elif duration < 120:
        n = 2
    else:
        n = 3

    chunk = duration / n
    return [
        {
            "scene_number": i + 1,
            "start_time":   round(i * chunk, 2),
            "end_time":     round((i + 1) * chunk, 2),
        }
        for i in range(n)
    ]


def detect_scenes(video_path: str, max_scenes: int = 100) -> List[dict]:
    """
    Detect scenes using PySceneDetect content detector.

    Always returns at least one scene — if PySceneDetect finds none (common
    for short or visually uniform clips), we divide the video evenly.
    """
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector

        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=27.0))
        scene_manager.detect_scenes(video, show_progress=False)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            logger.info("PySceneDetect found 0 scenes — using evenly-spaced fallback")
            return _fallback_scenes(video_path)

        scenes = [
            {
                "scene_number": i + 1,
                "start_time":   start.get_seconds(),
                "end_time":     end.get_seconds(),
            }
            for i, (start, end) in enumerate(scene_list[:max_scenes])
        ]
        logger.info(f"Detected {len(scenes)} scenes in {video_path}")
        return scenes

    except Exception as e:
        logger.warning(f"Scene detection failed, using fallback: {e}")
        return _fallback_scenes(video_path)


def extract_keyframe(video_path: str, scene: dict, output_dir: str) -> str:
    """Extract the representative keyframe (mid-scene). Returns JPG path."""
    os.makedirs(output_dir, exist_ok=True)
    mid_time   = (scene["start_time"] + scene["end_time"]) / 2
    scene_num  = scene["scene_number"]
    output_path = os.path.join(output_dir, f"scene_{scene_num:04d}.jpg")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(mid_time * fps))
    ret, frame = cap.read()
    cap.release()

    if ret and frame is not None:
        h, w = frame.shape[:2]
        if w > 640:
            frame = cv2.resize(frame, (640, int(h * (640 / w))))
        cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return output_path

    logger.warning(f"Could not extract frame at t={mid_time:.1f}s for scene {scene_num}")
    return ""


def deduplicate_descriptions(descriptions: List[str], threshold: float = 0.85) -> List[str]:
    """Remove near-duplicate scene descriptions using token overlap."""
    if not descriptions:
        return descriptions

    def overlap(a: str, b: str) -> float:
        ta, tb = set(a.lower().split()), set(b.lower().split())
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / max(len(ta), len(tb))

    deduped = [descriptions[0]]
    for desc in descriptions[1:]:
        if all(overlap(desc, e) < threshold for e in deduped):
            deduped.append(desc)
        else:
            deduped.append(desc)
    return deduped
