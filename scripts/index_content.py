#!/usr/bin/env python3
"""
Index accepted TSP content into ai_content_chunks table for RAG.

Features:
- Sentence-aware semantic chunking with hierarchical metadata prefixing.
- Multi-source text extraction (PDF documents, external links, inline descriptions).
- Batch embedding generation using sentence-transformers/all-MiniLM-L6-v2 (384-dim).
- Support for indexing a single training or all active trainings (--all).
- Idempotent upsert or clean refresh (--force-refresh).

Usage:
    python -m scripts.index_content <training_id> [--force-refresh]
    python -m scripts.index_content --all [--force-refresh]
"""

import asyncio
import argparse
import sys
import os
import time
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.tsp_client import TSPClient
from app.retrieval import (
    semantic_chunk_text,
    embed_texts,
    extract_text_from_link,
    get_embedder_info,
)


async def index_training_content(
    training_id: str,
    client: TSPClient,
    force_refresh: bool = False,
    extract_remote_links: bool = True,
) -> Dict[str, Any]:
    """
    Index all accepted content for a specific training into ai_content_chunks.
    
    Returns summary dict with chunk counts, contents processed, and time taken.
    """
    start_time = time.time()
    
    # 1. Fetch training metadata for contextual prefixing
    training_profile = await client.get_training_profile(training_id)
    training_title = training_profile.get("training", {}).get("title", "Training") if training_profile else "Training"
    
    # 2. Fetch accepted content items
    contents = await client.get_accepted_content(training_id)
    if not contents:
        print(f"[{training_id[:8]}] No accepted content items found for training '{training_title}'")
        return {
            "training_id": training_id,
            "training_title": training_title,
            "contents_found": 0,
            "chunks_upserted": 0,
            "duration_sec": round(time.time() - start_time, 2),
        }

    print(f"\n[{training_id[:8]}] Indexing '{training_title}' — {len(contents)} accepted content item(s)...")

    # 3. Optional clean wipe
    if force_refresh:
        deleted = await client.delete_training_chunks(training_id)
        print(f"  Cleaned {deleted} previous chunk(s) from DB.")

    total_chunks_for_training = 0
    chunks_to_insert = []

    # 4. Extract and chunk each content item
    for content in contents:
        content_id = str(content["id"])
        module_id = str(content["module_id"])
        lesson_id = str(content["lesson_id"]) if content.get("lesson_id") else None
        module_name = content.get("module_name", "General Module")
        lesson_name = content.get("lesson_name", "General Lesson")
        file_type = content.get("file_type", "TEXT")
        level = content.get("level", "MODULE")
        link = content.get("link", "")
        name = content.get("name", "")
        description = content.get("description", "")

        # Try extracting external/PDF document content if available
        extracted_text = ""
        if extract_remote_links and link:
            try:
                extracted_text = extract_text_from_link(link) or ""
                if extracted_text:
                    print(f"  [OK] Extracted {len(extracted_text.split())} words from document: {name} ({file_type})")
            except Exception as e:
                print(f"  [WARN] Failed link extraction for {name}: {e}")

        # Combine module concepts, lesson objectives, and document text
        text_components = []
        if content.get("module_key_concepts"):
            text_components.append(f"Module Key Concepts: {content['module_key_concepts']}")
        if content.get("module_teaching_strategy"):
            text_components.append(f"Teaching & Facilitation Strategy: {content['module_teaching_strategy']}")
        if content.get("lesson_objective"):
            text_components.append(f"Lesson Objective: {content['lesson_objective']}")
        if content.get("lesson_description"):
            text_components.append(f"Lesson Description: {content['lesson_description']}")
        if name:
            text_components.append(f"Resource Title: {name}")
        if description:
            text_components.append(f"Resource Summary: {description}")
        if extracted_text:
            text_components.append(f"Detailed Learning Material:\n{extracted_text}")

        combined_text = "\n\n".join(text_components).strip()
        if not combined_text:
            print(f"  [SKIP] {content_id} ({name}) -- no text available")
            continue

        # Hierarchical context header
        context_header = (
            f"[Training: {training_title} | Module: {module_name} | "
            f"Lesson: {lesson_name} | Level: {level} | Type: {file_type}]"
        )

        # Semantic sentence-aware chunking
        raw_chunks = semantic_chunk_text(
            combined_text,
            context_header=context_header,
            target_words=350,
            overlap_sentences=2,
        )

        if not raw_chunks:
            continue

        # Hard cap: any chunk exceeding MAX_CHUNK_CHARS is word-split into sub-chunks
        MAX_CHUNK_CHARS = 4000
        final_chunks = []
        for raw in raw_chunks:
            if len(raw) <= MAX_CHUNK_CHARS:
                final_chunks.append(raw)
            else:
                words = raw.split()
                chunk_size_words = MAX_CHUNK_CHARS // 6  # ~6 chars/word average
                sub_start = 0
                while sub_start < len(words):
                    sub_end = min(sub_start + chunk_size_words, len(words))
                    final_chunks.append(" ".join(words[sub_start:sub_end]))
                    if sub_end == len(words):
                        break
                    sub_start = sub_end - 30  # small word overlap

        for i, chunk_text in enumerate(final_chunks):
            chunks_to_insert.append({
                "content_id": content_id,
                "module_id": module_id,
                "lesson_id": lesson_id,
                "chunk_text": chunk_text,
                "chunk_index": i,
                "file_type": file_type,
                "level": level,
            })

    # 5. Batch embedding generation
    if chunks_to_insert:
        raw_texts = [c["chunk_text"] for c in chunks_to_insert]
        embeddings = embed_texts(raw_texts)

        # 6. Database Upsert
        async with client._pool.acquire() as conn:
            for item, emb in zip(chunks_to_insert, embeddings):
                await conn.execute("""
                    INSERT INTO ai_content_chunks
                        (content_id, module_id, lesson_id, chunk_text, chunk_index,
                         embedding, file_type, level)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8)
                    ON CONFLICT (content_id, chunk_index)
                    DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding  = EXCLUDED.embedding,
                        file_type  = EXCLUDED.file_type,
                        level      = EXCLUDED.level
                """,
                    item["content_id"],
                    item["module_id"],
                    item["lesson_id"],
                    item["chunk_text"],
                    item["chunk_index"],
                    emb,
                    item["file_type"],
                    item["level"],
                )
                total_chunks_for_training += 1

    total_in_db = await client.count_training_chunks(training_id)
    duration = round(time.time() - start_time, 2)
    print(f"  [OK] Finished [{training_id[:8]}]: {total_chunks_for_training} chunk(s) indexed in {duration}s. (Total in DB: {total_in_db})")

    return {
        "training_id": training_id,
        "training_title": training_title,
        "contents_found": len(contents),
        "chunks_upserted": total_chunks_for_training,
        "total_in_db": total_in_db,
        "duration_sec": duration,
    }


async def main():
    parser = argparse.ArgumentParser(description="Index TSP accepted content for RAG retrieval.")
    parser.add_argument("training_id", nargs="?", default=None, help="UUID of specific training to index")
    parser.add_argument("--all", action="store_true", help="Index all active trainings in the database")
    parser.add_argument("--force-refresh", action="store_true", help="Delete existing chunks before indexing")
    parser.add_argument("--no-remote", action="store_true", help="Skip remote/PDF document extraction")
    args = parser.parse_args()

    if not args.all and not args.training_id:
        parser.print_help()
        sys.exit(1)

    embedder_info = get_embedder_info()
    print(f"=== TSP RAG Content Indexer ===")
    print(f"Active Embedder: {embedder_info['name']} (Real MiniLM: {embedder_info['is_real']})")

    async with TSPClient() as client:
        if args.all:
            trainings = await client.get_all_trainings()
            print(f"Found {len(trainings)} active training(s) in TSP database.\n")
            summaries = []
            for t in trainings:
                tid = str(t["id"])
                res = await index_training_content(
                    training_id=tid,
                    client=client,
                    force_refresh=args.force_refresh,
                    extract_remote_links=not args.no_remote,
                )
                summaries.append(res)
            
            total_chunks = sum(s["chunks_upserted"] for s in summaries)
            print(f"\n==========================================")
            print(f"Batch Indexing Complete!")
            print(f"Trainings Processed: {len(summaries)}")
            print(f"Total Chunks Upserted: {total_chunks}")
            print(f"==========================================")
        else:
            await index_training_content(
                training_id=args.training_id,
                client=client,
                force_refresh=args.force_refresh,
                extract_remote_links=not args.no_remote,
            )


if __name__ == "__main__":
    asyncio.run(main())
