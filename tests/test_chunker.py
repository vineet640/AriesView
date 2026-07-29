"""Unit tests for the semantic chunker — the most logic-dense component,
where a silent bug would corrupt retrieval. The embed function is faked so
similarity between adjacent sentences is fully controlled."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "ingestion"))

import numpy as np
from chunker import chunk_blocks, split_sentences


def fake_embed_factory(vector_map):
    """Return an embed function assigning a fixed vector per sentence."""

    def embed(sentences):
        return [vector_map[s] for s in sentences]

    return embed


SIMILAR_A = np.array([1.0, 0.0])
SIMILAR_B = np.array([0.95, 0.31225])  # cosine ~0.95 with SIMILAR_A
DIFFERENT = np.array([0.0, 1.0])  # cosine 0 with SIMILAR_A


def test_split_sentences():
    text = "The lease begins Jan 1. Rent is $42 psf. Tenant may terminate early."
    assert len(split_sentences(text)) == 3


def test_boundary_placed_when_similarity_drops():
    s1, s2, s3 = "Rent is due monthly.", "Rent escalates 3% yearly.", "Tenant may terminate early."
    embed = fake_embed_factory({s1: SIMILAR_A, s2: SIMILAR_B, s3: DIFFERENT})
    blocks = [{"section_label": "Lease Terms", "text": f"{s1} {s2} {s3}"}]
    chunks = chunk_blocks(blocks, "doc1", embed)
    assert len(chunks) == 2
    assert chunks[0]["text"] == f"{s1} {s2}"
    assert chunks[1]["text"] == s3


def test_no_boundary_when_sentences_similar():
    s1, s2 = "Rent is due monthly.", "Rent escalates 3% yearly."
    embed = fake_embed_factory({s1: SIMILAR_A, s2: SIMILAR_B})
    blocks = [{"section_label": "Rent", "text": f"{s1} {s2}"}]
    chunks = chunk_blocks(blocks, "doc1", embed)
    assert len(chunks) == 1


def test_metadata_tagging_and_position_index():
    s1, s2 = "Rent is due monthly.", "Tenant may terminate early."
    embed = fake_embed_factory({s1: SIMILAR_A, s2: DIFFERENT})
    blocks = [
        {"section_label": "Rent Provisions", "text": s1},
        {"section_label": "Termination Clause", "text": s2},
    ]
    chunks = chunk_blocks(blocks, "doc42", embed)
    assert [c["position_index"] for c in chunks] == [0, 1]
    assert chunks[0]["section_label"] == "Rent Provisions"
    assert chunks[1]["section_label"] == "Termination Clause"
    assert all(c["document_id"] == "doc42" for c in chunks)


def test_chunks_never_cross_section_boundaries():
    s1, s2 = "Rent is due monthly.", "Rent escalates 3% yearly."
    embed = fake_embed_factory({s1: SIMILAR_A, s2: SIMILAR_B})
    blocks = [
        {"section_label": "Rent", "text": s1},
        {"section_label": "Escalations", "text": s2},
    ]
    chunks = chunk_blocks(blocks, "doc1", embed)
    assert len(chunks) == 2  # similar sentences, but different sections


def test_empty_blocks_skipped():
    chunks = chunk_blocks([{"section_label": "X", "text": "   "}], "doc1", lambda s: [])
    assert chunks == []
