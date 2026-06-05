"""Sentence-transformers embedder — always local, used by both providers."""
from functools import lru_cache
from typing import List
import numpy as np


@lru_cache(maxsize=1)
def _get_model(model_name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name)


def embed_texts(texts: List[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    if not texts:
        return np.empty((0, 384), dtype=np.float32)
    model = _get_model(model_name)
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return vectors.astype(np.float32)
