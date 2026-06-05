"""Stage 9: Build FAISS index from transcript segments + scene descriptions."""
import os
import json
import logging
import pickle
from typing import List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


def build_faiss_index(
    transcript_segments: List[dict],
    scenes: List[dict],
    provider,
    output_dir: str,
    video_id: str,
) -> Tuple[str, str]:
    """
    Embed all segments and scene descriptions and save FAISS index + metadata.
    Returns (index_path, metadata_path).
    """
    import faiss
    os.makedirs(output_dir, exist_ok=True)

    texts = []
    metadata = []

    for seg in transcript_segments:
        text = seg.get("text", "").strip()
        if text:
            texts.append(text)
            metadata.append({
                "type": "transcript",
                "text": text,
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "label": "Transcript",
            })

    for scene in scenes:
        desc = scene.get("description", "").strip()
        if desc:
            texts.append(desc)
            metadata.append({
                "type": "scene",
                "text": desc,
                "start": scene.get("start_time", 0),
                "end": scene.get("end_time", 0),
                "label": scene.get("scene_label") or f"Scene {scene.get('scene_number', '?')}",
            })

    if not texts:
        logger.warning("No texts to embed — returning empty index.")
        return "", ""

    vectors = provider.embed(texts)
    dim = vectors.shape[1]

    index = faiss.IndexFlatIP(dim)  # Inner product (cosine after normalization)
    faiss.normalize_L2(vectors)
    index.add(vectors)

    index_path = os.path.join(output_dir, f"{video_id}_faiss.index")
    metadata_path = os.path.join(output_dir, f"{video_id}_faiss_meta.json")

    faiss.write_index(index, index_path)
    with open(metadata_path, "w") as f:
        json.dump(metadata, f)

    logger.info(f"Built FAISS index with {len(texts)} entries.")
    return index_path, metadata_path


def search_index(
    query: str,
    index_path: str,
    metadata_path: str,
    provider,
    top_k: int = 5,
) -> List[dict]:
    """Search FAISS index with a text query. Returns top_k results with metadata."""
    import faiss
    if not index_path or not os.path.exists(index_path):
        return []

    index = faiss.read_index(index_path)
    with open(metadata_path) as f:
        metadata = json.load(f)

    query_vec = provider.embed([query])
    faiss.normalize_L2(query_vec)
    distances, indices = index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        item = dict(metadata[idx])
        item["score"] = float(dist)
        results.append(item)
    return results


def search_time_range(
    start: float,
    end: float,
    transcript_segments: List[dict],
    scenes: List[dict],
) -> List[dict]:
    """Return all transcript segments and scenes overlapping [start, end]."""
    results = []
    for seg in transcript_segments:
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)
        if seg_end >= start and seg_start <= end:
            results.append({
                "type": "transcript",
                "text": seg.get("text", ""),
                "start": seg_start,
                "end": seg_end,
                "label": "Transcript",
            })
    for scene in scenes:
        sc_start = scene.get("start_time", 0)
        sc_end = scene.get("end_time", 0)
        if sc_end >= start and sc_start <= end:
            desc = scene.get("description", "")
            if desc:
                results.append({
                    "type": "scene",
                    "text": desc,
                    "start": sc_start,
                    "end": sc_end,
                    "label": scene.get("scene_label") or f"Scene {scene.get('scene_number', '?')}",
                })
    return results
