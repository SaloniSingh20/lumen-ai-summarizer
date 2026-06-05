"""ONNX-based embedder via fastembed — no PyTorch required."""
from functools import lru_cache
from typing import List
import numpy as np


@lru_cache(maxsize=1)
def _get_model(_ignored_name: str):
    from fastembed import TextEmbedding
    # BAAI/bge-small-en-v1.5: 384-dim, ~130 MB download, ONNX runtime
    return TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def embed_texts(texts: List[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    if not texts:
        return np.empty((0, 384), dtype=np.float32)
    model = _get_model(model_name)
    vectors = list(model.embed(texts))
    return np.array(vectors, dtype=np.float32)
