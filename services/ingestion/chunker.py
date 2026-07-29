"""Semantic chunking.

Each sentence is embedded with SBERT; cosine similarity is computed between
adjacent sentences, and a chunk boundary is placed when similarity drops
below the threshold (0.75) — a drop in similarity signals a shift in topic
or meaning, which is a more natural split point than a fixed character
count. Chunks never cross section boundaries, so a termination clause stays
intact rather than being cut mid-clause.

The embed function is injected so the chunker can be unit-tested without a
model, and so the ingestion service can point it at the embedding
microservice.
"""

import re
from typing import Callable

import numpy as np

SIMILARITY_THRESHOLD = 0.75
MAX_SENTENCES_PER_CHUNK = 12

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def chunk_blocks(
    blocks: list[dict],
    document_id: str,
    embed: Callable[[list[str]], list[list[float]]],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Chunk parsed blocks semantically, tagging each chunk with metadata.

    Returns chunks shaped for Weaviate: text plus document_id,
    section_label, and position_index.
    """
    chunks = []
    position = 0
    for block in blocks:
        sentences = split_sentences(block["text"])
        if not sentences:
            continue
        if len(sentences) == 1:
            groups = [sentences]
        else:
            vectors = [np.asarray(v) for v in embed(sentences)]
            groups = [[sentences[0]]]
            for i in range(1, len(sentences)):
                similarity = _cosine(vectors[i - 1], vectors[i])
                if similarity < threshold or len(groups[-1]) >= MAX_SENTENCES_PER_CHUNK:
                    groups.append([])
                groups[-1].append(sentences[i])
        for group in groups:
            chunks.append(
                {
                    "text": " ".join(group),
                    "document_id": document_id,
                    "section_label": block["section_label"],
                    "position_index": position,
                }
            )
            position += 1
    return chunks
