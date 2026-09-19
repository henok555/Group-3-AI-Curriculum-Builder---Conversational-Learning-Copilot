#!/usr/bin/env python3
"""
generate_curriculum.py — CLI script for standalone curriculum generation.

Generates a structured curriculum for a TSP training using the same pipeline
as the FastAPI endpoint, without needing the full server running.

Usage:
    python scripts/generate_curriculum.py <training_id> [--out FILE] [--force]

Examples:
    # Generate and print to stdout
    python scripts/generate_curriculum.py 45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc

    # Save to JSON file
    python scripts/generate_curriculum.py 45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc --out output.json

    # Force regenerate even if a cached version exists in the DB
    python scripts/generate_curriculum.py 45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc --force

Requires:
    - .env file with OPENROUTER_API_KEY, TSP_DB_* credentials
    - TSP database accessible from this host
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path so `app.*` imports work when run from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.tsp_client import TSPClient
from app.curriculum_builder import generate_curriculum


async def main(training_id: str, output_file: str | None, force: bool) -> None:
    print(f"\n[CurriculumCLI] Starting for training_id: {training_id}")
    print(f"[CurriculumCLI] Force regenerate: {force}")

    async with TSPClient() as db:
        # ── Check training exists ─────────────────────────────────────────
        print("[CurriculumCLI] Fetching training profile...")
        training_profile = await db.get_training_profile(training_id)
        if not training_profile.get("training"):
            print(f"[ERROR] Training '{training_id}' not found in TSP database.")
            sys.exit(1)

        title = training_profile["training"].get("title", "Unknown")
        print(f"[CurriculumCLI] Training: {title}")

        # ── Check cache ───────────────────────────────────────────────────
        if not force:
            cached = await db.get_latest_curriculum(training_id)
            if cached:
                print("[CurriculumCLI] Found cached curriculum in DB — returning cached version.")
                print("[CurriculumCLI] Use --force to regenerate.")
                _output(cached, output_file)
                return

        # ── Fetch context data ────────────────────────────────────────────
        print("[CurriculumCLI] Fetching modules, audience profile...")
        modules = await db.get_modules_with_lessons(training_id)
        audience = await db.get_audience_profile(training_id)

        print(f"[CurriculumCLI] Loaded {len(modules)} modules")
        print(f"[CurriculumCLI] Learner level: {audience.get('learner_level', 'N/A')}")

        # ── Generate ──────────────────────────────────────────────────────
        print("[CurriculumCLI] Calling Gemma via OpenRouter... (may take 60–120s)")
        start = datetime.utcnow()

        curriculum, report = await generate_curriculum(
            training_id=training_id,
            training_profile=training_profile,
            modules=modules,
            audience=audience,
        )

        elapsed = (datetime.utcnow() - start).total_seconds()
        print(f"[CurriculumCLI] Generated in {elapsed:.1f}s")

        # ── Validation report ─────────────────────────────────────────────
        print("\n[Validation Report]")
        print(f"  Rubric weights normalized : {report.rubrics_weight_normalized}")
        print(f"  Rubric criteria padded    : {report.rubrics_criteria_padded}")
        print(f"  Lesson objectives filled  : {report.lessons_objective_filled}")
        print(f"  Assignments auto-added    : {report.modules_assignment_added}")
        print(f"  Assessments auto-added    : {report.modules_assessment_added}")
        print(f"  Rubrics auto-added        : {report.modules_rubric_added}")
        print(f"  Objectives map inferred   : {report.objectives_mapping_inferred}")

        # ── Stats ─────────────────────────────────────────────────────────
        total_lessons = sum(len(m.lessons) for m in curriculum.modules)
        print(f"\n[Curriculum Stats]")
        print(f"  Modules  : {len(curriculum.modules)}")
        print(f"  Lessons  : {total_lessons}")
        print(f"  Title    : {curriculum.training_title}")

        # ── Save to DB ────────────────────────────────────────────────────
        try:
            curriculum_dict = curriculum.model_dump(mode="json")
            curriculum_dict["validation_report"] = report.model_dump()
            db_id = await db.save_generated_curriculum(training_id, curriculum_dict)
            print(f"[CurriculumCLI] Saved to DB with id: {db_id}")
        except Exception as e:
            print(f"[Warning] Failed to save to DB: {e}")
            curriculum_dict = curriculum.model_dump(mode="json")

        _output(curriculum_dict, output_file)


def _output(data: dict, output_file: str | None) -> None:
    """Print JSON to stdout or write to file."""
    json_str = json.dumps(data, indent=2, default=str)
    if output_file:
        Path(output_file).write_text(json_str, encoding="utf-8")
        print(f"[CurriculumCLI] Curriculum written to: {output_file}")
    else:
        print("\n" + "─" * 60)
        print(json_str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a TSP curriculum from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "training_id",
        help="UUID of the training in the TSP database"
    )
    parser.add_argument(
        "--out", "-o",
        metavar="FILE",
        help="Write curriculum JSON to this file (default: stdout)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force regeneration even if a cached curriculum exists"
    )
    args = parser.parse_args()
    asyncio.run(main(args.training_id, args.out, args.force))
