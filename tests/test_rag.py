"""
Unit and integration tests for RAG chunking, extraction, embedding, and retrieval components.
"""

import pytest
import numpy as np
from app.retrieval import (
    split_into_sentences,
    semantic_chunk_text,
    chunk_text,
    cosine_similarity,
    FallbackEmbedder,
    extract_text_from_pdf_bytes,
    extract_text_from_link,
    embed_text,
    embed_texts,
)


def test_split_into_sentences_basic():
    text = "Facilitation is key. It ensures active participation. E.g. using interactive polls helps."
    sentences = split_into_sentences(text)
    assert len(sentences) >= 2
    assert any("Facilitation is key." in s for s in sentences)
    # Check abbreviation doesn't cause broken single-letter sentences
    assert not any(s == "E." or s == "g." for s in sentences)


def test_split_into_sentences_empty():
    assert split_into_sentences("") == []
    assert split_into_sentences("   ") == []


def test_semantic_chunk_text_with_context_header():
    paragraphs = (
        "Module 1 introduces fundamental facilitation concepts. "
        "Trainers must understand group dynamics and adult learning principles. "
        "Engaging participants requires empathy and active listening skills. "
        "Assessment strategies must align with intended learning outcomes."
    )
    header = "[Training: Demo | Module: M1 | Lesson: L1 | Level: MODULE]"
    chunks = semantic_chunk_text(paragraphs, context_header=header, target_words=20, overlap_sentences=1)
    
    assert len(chunks) >= 1
    for chunk in chunks:
        assert header in chunk
        assert "Module 1" in chunk or "Trainers" in chunk or "Assessment" in chunk


def test_cosine_similarity_orthogonality_and_identity():
    # Identical unit vectors
    v1 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v1), 0.0001) == 1.0

    # Orthogonal vectors
    v2 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), 0.0001) == 0.0

    # Opposite vectors
    v3 = [-1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3), 0.0001) == -1.0


def test_fallback_embedder_dimension_and_normalization():
    embedder = FallbackEmbedder(dim=384)
    res = embedder.encode("This is a test query about training facilitation")
    assert len(res) == 384
    norm = np.linalg.norm(res)
    assert pytest.approx(norm, 0.001) == 1.0


def test_embed_text_dimension():
    vec = embed_text("What are trainer competencies?")
    assert len(vec) == 384
    norm = np.linalg.norm(vec)
    assert pytest.approx(norm, 0.001) == 1.0


def test_extract_text_from_pdf_bytes_invalid():
    # Corrupt or empty bytes should not raise an unhandled exception
    res = extract_text_from_pdf_bytes(b"not a valid pdf content")
    assert res == ""


def test_extract_text_from_link_invalid_url():
    # Non-existent local file or malformed link returns None gracefully
    assert extract_text_from_link("") is None
    assert extract_text_from_link("non_existent_file_path_12345.pdf") is None
