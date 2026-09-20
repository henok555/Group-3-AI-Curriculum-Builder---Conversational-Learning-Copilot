"""
Retrieval module for RAG — reads from ai_content_chunks table.

pgvector is NOT available on this PostgreSQL server. Embeddings are stored
as float[] columns and cosine similarity is computed in Python (numpy dot
product on pre-normalized vectors).

For production at scale (>100k chunks), replace with a vector DB or install
pgvector and switch to: ORDER BY embedding <=> $1 LIMIT k
"""

import io
import re
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


COMMON_ABBREVIATIONS = {
    "e.g.", "i.e.", "dr.", "mr.", "mrs.", "ms.", "prof.", "vs.", "approx.",
    "etc.", "vol.", "no.", "p.", "pp.", "dept.", "est.", "inc.", "corp.", "ltd."
}


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into distinct sentences respecting punctuation, numbers, and abbreviations.
    Handles headings, bullet points, and common abbreviations without mid-sentence cuts.
    """
    if not text:
        return []

    cleaned = re.sub(r"\r\n|\r", "\n", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    sentences = []

    for para in paragraphs:
        # Split on sentence-ending punctuation followed by whitespace or end of line
        raw_parts = re.split(r'([.!?]+(?:\s+|$))', para)
        current = ""
        for i in range(0, len(raw_parts), 2):
            text_part = raw_parts[i]
            punct_part = raw_parts[i + 1] if i + 1 < len(raw_parts) else ""
            combined_part = text_part + punct_part

            words = (current + text_part).strip().lower().split()
            last_word_with_punct = (words[-1] + punct_part.strip()).lower() if words else ""

            # If it's a known abbreviation, accumulate rather than split
            if any(last_word_with_punct == abbr or last_word_with_punct.endswith(abbr) for abbr in COMMON_ABBREVIATIONS):
                current += combined_part
            else:
                candidate = (current + combined_part).strip()
                if candidate:
                    sentences.append(candidate)
                current = ""

        if current.strip():
            sentences.append(current.strip())

    return sentences if sentences else [cleaned]


def semantic_chunk_text(
    text: str,
    context_header: str = "",
    target_words: int = 350,
    overlap_sentences: int = 2
) -> List[str]:
    """
    Sentence-aware semantic chunking with structural context header prefixing.
    
    Ensures:
    1. Chunks do not break sentences mid-thought.
    2. Overlap is sentence-aligned to retain semantic transitions.
    3. Structural metadata (e.g. [Module: ... | Lesson: ...]) is prefixed to each chunk.
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_word_count = 0

    header_prefix = f"{context_header.strip()}\n\n" if context_header.strip() else ""

    for sentence in sentences:
        words_in_sentence = len(sentence.split())
        
        # If adding this sentence exceeds target and we already have content
        if current_word_count + words_in_sentence > target_words and current_sentences:
            chunk_body = " ".join(current_sentences).strip()
            chunks.append(f"{header_prefix}{chunk_body}".strip())
            
            # Carry over overlap sentences
            overlap = current_sentences[-overlap_sentences:] if len(current_sentences) >= overlap_sentences else current_sentences
            current_sentences = list(overlap)
            current_word_count = sum(len(s.split()) for s in current_sentences)

        current_sentences.append(sentence)
        current_word_count += words_in_sentence

    if current_sentences:
        chunk_body = " ".join(current_sentences).strip()
        chunks.append(f"{header_prefix}{chunk_body}".strip())

    return chunks


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping word-based chunks (backward-compatible fallback).
    """
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


def extract_text_from_pdf_bytes(pdf_bytes: bytes, max_pages: int = 100) -> str:
    """Extract and clean text from raw PDF bytes using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted_pages = []
        for i, page in enumerate(reader.pages[:max_pages]):
            text = page.extract_text() or ""
            if text.strip():
                extracted_pages.append(text.strip())
        return "\n\n".join(extracted_pages).strip()
    except Exception as e:
        print(f"[Warning] PDF extraction error: {e}")
        return ""


def extract_text_from_link(link: str, timeout: int = 10) -> Optional[str]:
    """
    Download and extract text from external URL, Google Drive PDF, or local file path.
    Returns cleaned text or None if extraction fails.
    """
    if not link or not isinstance(link, str):
        return None
    
    link = link.strip()
    
    # 1. Local file path check
    if os.path.isfile(link):
        try:
            if link.lower().endswith(".pdf"):
                with open(link, "rb") as f:
                    return extract_text_from_pdf_bytes(f.read())
            else:
                with open(link, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read().strip()
        except Exception as e:
            print(f"[Warning] Failed reading local file {link}: {e}")
            return None

    # 2. Remote HTTP/HTTPS URL
    if link.startswith("http://") or link.startswith("https://"):
        try:
            import requests
            
            # Google Drive URL conversion
            target_url = link
            gdrive_match = re.search(r"drive\.google\.com/(?:file/d/|open\?id=)([a-zA-Z0-9_-]+)", link)
            if gdrive_match:
                file_id = gdrive_match.group(1)
                target_url = f"https://drive.google.com/uc?export=download&id={file_id}"

            resp = requests.get(target_url, timeout=timeout, headers={"User-Agent": "TSP-AI-RAG-Indexer/1.0"})
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "").lower()
                if "application/pdf" in content_type or link.lower().endswith(".pdf") or "drive.google.com" in link:
                    text = extract_text_from_pdf_bytes(resp.content)
                    if text:
                        return text
                # Plain text / markdown fallback
                return resp.text.strip()
        except Exception as e:
            print(f"[Warning] Failed fetching remote link {link}: {e}")
            return None

    return None


async def retrieve_relevant_chunks(
    tsp_client,          # TSPClient instance
    query: str,
    training_id: str,
    top_k: int = 5,
    similarity_threshold: float = 0.3,
    module_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    level: Optional[str] = None,
    file_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant content chunks for a query from ai_content_chunks with optional metadata filtering.

    Strategy (pgvector not available on host DB):
    1. Load chunks for this training (with optional module/lesson/level filters) from ai_content_chunks
    2. Embed the query using L2-normalized 384-dim embeddings
    3. Compute cosine similarity in Python via numpy dot product
    4. Apply similarity thresholding, deduplicate by content ID/chunk index, and return top-k
    """
    query_str = """
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
        WHERE m.training_id = $1::uuid
    """
    params = [training_id]
    
    if module_id:
        params.append(module_id)
        query_str += f" AND c.module_id = ${len(params)}::uuid"
    if lesson_id:
        params.append(lesson_id)
        query_str += f" AND c.lesson_id = ${len(params)}::uuid"
    if level:
        params.append(level)
        query_str += f" AND c.level = ${len(params)}"
    if file_type:
        params.append(file_type)
        query_str += f" AND c.file_type = ${len(params)}"

    try:
        async with tsp_client._pool.acquire() as conn:
            rows = await conn.fetch(query_str, *params)
    except Exception as e:
        print(f"[Warning] Failed executing chunk retrieval query: {e}")
        return []

    if not rows:
        return []

    query_embedding = embed_text(query)

    results = []
    seen_keys = set()

    for row in rows:
        emb = list(row["embedding"])  # asyncpg returns list[float] for float[]
        sim = cosine_similarity(query_embedding, emb)
        if sim >= similarity_threshold:
            dedup_key = (str(row["content_id"]), row["chunk_index"])
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

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
