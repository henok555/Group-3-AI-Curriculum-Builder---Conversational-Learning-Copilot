#!/usr/bin/env python3
"""
Index accepted TSP content into ai_content_chunks table for RAG.

Since pgvector is not available, embeddings are stored as float[] arrays.
Cosine similarity is computed in the application layer (retrieval.py).

Table created by:
    CREATE TABLE ai_content_chunks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        content_id UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
        module_id UUID NOT NULL REFERENCES modules(id),
        lesson_id UUID REFERENCES lessons(id),
        chunk_text TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        embedding float[] NOT NULL,
        file_type VARCHAR(50),
        level VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(content_id, chunk_index)
    );

Run:
    python -m scripts.index_content <training_id>
"""

import asyncio
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.tsp_client import TSPClient
from app.retrieval import chunk_text, embed_texts


async def index_training_content(training_id: str) -> int:
    """
    Index all accepted content for a training into ai_content_chunks.
    Returns total chunks inserted.
    """
    async with TSPClient() as client:
        contents = await client.get_accepted_content(training_id)
        print(f"Found {len(contents)} accepted content items for training {training_id}")

        total_upserted = 0

        async with client._pool.acquire() as conn:
            for content in contents:
                # Build text from available fields (description + name)
                # In production, PDF text would be extracted from content['link']
                text_parts = []
                if content.get("description"):
                    text_parts.append(content["description"])
                if content.get("name"):
                    text_parts.append(content["name"])

                full_text = " ".join(text_parts).strip()
                if not full_text:
                    print(f"  SKIP {content['id']} ({content.get('name','?')}) — no inline text")
                    continue

                chunks = chunk_text(full_text, chunk_size=400, overlap=50)
                chunk_texts_list = chunks
                embeddings = embed_texts(chunk_texts_list)

                print(f"  {content.get('name', '?')} ({content.get('file_type','?')}): "
                      f"{len(chunks)} chunk(s)")

                for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    # Upsert — on conflict (content_id, chunk_index) update text + embedding
                    await conn.execute("""
                        INSERT INTO ai_content_chunks
                            (content_id, module_id, lesson_id, chunk_text, chunk_index,
                             embedding, file_type, level)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (content_id, chunk_index)
                        DO UPDATE SET
                            chunk_text = EXCLUDED.chunk_text,
                            embedding  = EXCLUDED.embedding,
                            file_type  = EXCLUDED.file_type,
                            level      = EXCLUDED.level
                    """,
                        content["id"],
                        content["module_id"],
                        content.get("lesson_id"),
                        chunk,
                        i,
                        emb,           # asyncpg accepts list[float] for float[] columns
                        content.get("file_type"),
                        content.get("level"),
                    )
                    total_upserted += 1

        # Verify row count
        async with client._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as n FROM ai_content_chunks c "
                "JOIN modules m ON m.id = c.module_id "
                "WHERE m.training_id = $1",
                training_id
            )
            print(f"\nTotal chunks in DB for this training: {row['n']}")

        print(f"Upserted {total_upserted} chunk(s) total.")
        return total_upserted


async def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.index_content <training_id>")
        sys.exit(1)

    training_id = sys.argv[1]
    await index_training_content(training_id)


if __name__ == "__main__":
    asyncio.run(main())
