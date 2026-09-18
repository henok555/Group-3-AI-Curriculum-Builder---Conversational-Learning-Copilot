"""
Retrieval module for RAG — reads from ai_content_chunks table.

pgvector is NOT available on this PostgreSQL server. Embeddings are stored
as float[] columns and cosine similarity is computed in Python (numpy dot
product on pre-normalized vectors).

For production at scale (>100k chunks), replace with a vector DB or install
pgvector and switch to: ORDER BY embedding <=> $1 LIMIT k
"""

import os
import numpy as np
from typing import List, Dict, Any, Optional

# Embedding model — 384 dimensions, fast and good quality
# Matches the dimension used when indexing (scripts/index_content.py)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_embedding_model = None


class FallbackEmbedder:
    """Fallback 384-dim hashing embedder used when sentence-transformers is not available."""
    def __init__(self, dim: int = 384):
        self.dim = dim

    def encode(self, texts, normalize_embeddings: bool = True):
        is_single = isinstance(texts, str)
        text_list = [texts] if is_single else texts

        embeddings = []
        for txt in text_list:
            vec = np.zeros(self.dim, dtype=np.float32)
            words = txt.lower().split()
            for w in words:
                h = abs(hash(w)) % self.dim
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embeddings.append(vec.tolist() if not is_single else vec)

        if is_single:
            norm = np.linalg.norm(vec)
            return (vec / norm if norm > 0 else vec).tolist()
        return embeddings


_embedder_name = None
_embedder_error = None


def get_embedding_model(raise_on_failure: bool = False):
    global _embedding_model, _embedder_name, _embedder_error
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            _embedder_name = "minilm"
            _embedder_error = None
        except Exception as e:
            _embedder_error = str(e)
            if raise_on_failure:
                raise RuntimeError(f"Embedding model unavailable: {e}")
            _embedding_model = FallbackEmbedder(384)
            _embedder_name = "fallback"
    return _embedding_model


def get_embedder_info() -> dict:
    """Return embedder metadata (name, is_real, error)."""
    get_embedding_model()
    return {
        "name": _embedder_name or "unknown",
        "is_real": _embedder_name == "minilm",
        "error": _embedder_error
    }


def get_embedder_name() -> str:
    """Return the name of the active embedder ('minilm' or 'fallback')."""
    return get_embedder_info()["name"]


def embed_text(text: str) -> List[float]:
    """Generate L2-normalized embedding for a single text."""
    model = get_embedding_model()
    res = model.encode(text, normalize_embeddings=True)
    return res if isinstance(res, list) else res.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate L2-normalized embeddings for a batch of texts."""
    model = get_embedding_model()
    res = model.encode(texts, normalize_embeddings=True)
    return res if isinstance(res, list) else res.tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two pre-normalized vectors = dot product."""
    return float(np.dot(a, b))


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


async def retrieve_relevant_chunks(
    tsp_client,          # TSPClient instance
    query: str,
    training_id: str,
    top_k: int = 5,
    similarity_threshold: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant content chunks for a query from ai_content_chunks.

    Strategy (pgvector not available):
    1. Load all chunks for this training from ai_content_chunks table
    2. Embed the query
    3. Compute cosine similarity in Python
    4. Return top-k chunks above threshold with source attribution

    The DB query is filtered by training_id via the modules join, so we
    only load chunks relevant to this training — not the full table.
    """
    async with tsp_client._pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                c.id,
                c.content_id,
                c.module_id,
                c.lesson_id,
                c.chunk_text,
                c.chunk_index,
                c.embedding,
                c.file_type,
                c.level,
                m.name  AS module_name,
                l.name  AS lesson_name
            FROM ai_content_chunks c
            JOIN modules m ON m.id = c.module_id
            LEFT JOIN lessons l ON l.id = c.lesson_id
            WHERE m.training_id = $1
        """, training_id)

    if not rows:
        return []

    query_embedding = embed_text(query)

    results = []
    for row in rows:
        emb = list(row["embedding"])  # asyncpg returns list[float] for float[]
        sim = cosine_similarity(query_embedding, emb)
        if sim >= similarity_threshold:
            results.append({
                "content_id": str(row["content_id"]),
                "chunk_id":   str(row["id"]),
                "module_id":  str(row["module_id"]),
                "lesson_id":  str(row["lesson_id"]) if row["lesson_id"] else None,
                "chunk_text": row["chunk_text"],
                "chunk_index": row["chunk_index"],
                "file_type":  row["file_type"],
                "level":      row["level"],
                "module_name": row["module_name"],
                "lesson_name": row["lesson_name"],
                "similarity": sim,
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


# pgvector-ready schema — run when pgvector becomes available
PGVECTOR_SCHEMA = """
-- Run ONLY when pgvector extension is installed:
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop the float[] fallback table first, then recreate:
DROP TABLE IF EXISTS ai_content_chunks;
CREATE TABLE ai_content_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    module_id         UUID NOT NULL REFERENCES modules(id),
    lesson_id         UUID REFERENCES lessons(id),
    chunk_text        TEXT NOT NULL,
    chunk_index       INTEGER NOT NULL,
    embedding         VECTOR(384),   -- all-MiniLM-L6-v2
    file_type         VARCHAR(50),
    level             VARCHAR(50),
    created_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE(content_id, chunk_index)
);

-- IVFFlat index for cosine-distance ANN search
CREATE INDEX idx_ai_chunks_embedding
ON ai_content_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Then update the retrieval query to:
-- ORDER BY embedding <=> $1::vector LIMIT $2
"""
