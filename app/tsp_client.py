"""
TSPClient — Data Access Layer for TSP PostgreSQL Database

Single class wrapping asyncpg connection pool. All queries parameterized.
Only place in codebase allowed to touch TSP tables directly.
"""

import os
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass
class TSPConfig:
    host: str = os.getenv("TSP_DB_HOST", "localhost")
    port: int = int(os.getenv("TSP_DB_PORT", "5432"))
    user: str = os.getenv("TSP_DB_USER", "postgres")
    password: str = os.getenv("TSP_DB_PASSWORD", "postgres")
    database: str = os.getenv("TSP_DB_NAME", "training_solutions")
    min_size: int = int(os.getenv("TSP_DB_POOL_MIN", "2"))
    max_size: int = int(os.getenv("TSP_DB_POOL_MAX", "10"))


class TSPClient:
    """Async data access client for TSP database."""

    def __init__(self, config: Optional[TSPConfig] = None):
        self.config = config or TSPConfig()
        self._pool: Optional[Pool] = None

    async def connect(self) -> None:
        """Initialize connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
            )

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def __aenter__(self) -> "TSPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # ==================== Training Profile ====================

    async def get_training_profile(self, training_id: str) -> dict:
        """
        Get complete training profile including training, audience profile,
        objectives, outcomes, keywords, purposes, and company info.
        """
        async with self._pool.acquire() as conn:
            # Training base info + company + type
            training_row = await conn.fetchrow("""
                SELECT t.*, cp.name as company_name, cp.verification_status as company_status,
                       bt.name as business_type, it.name as industry_type,
                       tt.name as training_type_name
                FROM trainings t
                LEFT JOIN company_profiles cp ON cp.id = t.company_profile_id
                LEFT JOIN base_data.business_types bt ON bt.id = cp.business_type_id
                LEFT JOIN base_data.industry_types it ON it.id = cp.industry_type_id
                LEFT JOIN base_data.training_types tt ON tt.id = t.training_type_id
                WHERE t.id = $1 AND t.is_deleted = false
            """, training_id)

            if not training_row:
                return {}

            # Audience profile
            audience_row = await conn.fetchrow("""
                SELECT ap.*, 
                       el.name as education_level, el.description as education_level_desc,
                       l.name as language_name, l.code as language_code,
                       ll.name as learner_level, ll.description as learner_level_desc,
                       we.name as work_experience, we.description as work_experience_desc
                FROM audience_profiles ap
                LEFT JOIN base_data.education_levels el ON el.id = ap.education_level_id
                LEFT JOIN base_data.languages l ON l.id = ap.language_id
                LEFT JOIN base_data.learner_levels ll ON ll.id = ap.learner_level_id
                LEFT JOIN base_data.work_experiences we ON we.id = ap.work_experience_id
                WHERE ap.training_id = $1
            """, training_id)

            # Objectives (hierarchical)
            objectives_rows = await conn.fetch("""
                SELECT o.id, o.definition, o.objective_id as parent_id
                FROM objectives o
                WHERE o.training_id = $1
                ORDER BY o.created_at
            """, training_id)

            # Outcomes
            outcomes_rows = await conn.fetch("""
                SELECT oc.id, oc.definition, oc.objective_id
                FROM outcomes oc
                JOIN objectives o ON o.id = oc.objective_id
                WHERE o.training_id = $1
            """, training_id)

            # Keywords
            keywords_rows = await conn.fetch("""
                SELECT keywords FROM training_keywords WHERE training_id = $1
            """, training_id)

            # Purposes
            purposes_rows = await conn.fetch("""
                SELECT tp.name FROM trainings_purposes tpur
                JOIN base_data.training_purposes tp ON tp.id = tpur.purpose_id
                WHERE tpur.training_id = $1
            """, training_id)

            # Build objectives tree
            objectives_by_id = {row["id"]: {"id": row["id"], "definition": row["definition"], "children": []} for row in objectives_rows}
            root_objectives = []
            for row in objectives_rows:
                obj = objectives_by_id[row["id"]]
                if row["parent_id"] and row["parent_id"] in objectives_by_id:
                    objectives_by_id[row["parent_id"]]["children"].append(obj)
                else:
                    root_objectives.append(obj)

            # Attach outcomes to objectives
            for row in outcomes_rows:
                obj_id = row["objective_id"]
                if obj_id in objectives_by_id:
                    if "outcomes" not in objectives_by_id[obj_id]:
                        objectives_by_id[obj_id]["outcomes"] = []
                    objectives_by_id[obj_id]["outcomes"].append({"id": row["id"], "definition": row["definition"]})

            return {
                "training": dict(training_row),
                "audience_profile": dict(audience_row) if audience_row else {},
                "objectives": root_objectives,
                "keywords": [r["keywords"] for r in keywords_rows],
                "purposes": [r["name"] for r in purposes_rows],
            }

    # ==================== Modules with Lessons ====================

    async def get_modules_with_lessons(self, training_id: str) -> list[dict]:
        """Get all modules for a training with their lessons and details."""
        async with self._pool.acquire() as conn:
            # Modules
            modules_rows = await conn.fetch("""
                SELECT m.*, tt.name as training_tag_name,
                       ti.name as technology_integration_name, ti.description as tech_integration_desc
                FROM modules m
                LEFT JOIN base_data.training_tags tt ON tt.id = m.training_tag_id
                LEFT JOIN base_data.technology_integrations ti ON ti.id = m.technology_integration_id
                WHERE m.training_id = $1
                ORDER BY m.module_order
            """, training_id)

            modules = []
            for m_row in modules_rows:
                module_id = m_row["id"]
                module_dict = dict(m_row)

                # Lessons
                lessons_rows = await conn.fetch("""
                    SELECT l.* FROM lessons l
                    WHERE l.module_id = $1
                    ORDER BY l.created_at
                """, module_id)

                lessons = []
                for l_row in lessons_rows:
                    lesson_id = l_row["id"]
                    lesson_dict = dict(l_row)

                    # Lesson instructional methods
                    lim_rows = await conn.fetch("""
                        SELECT im.name, im.description
                        FROM lesson_instructional_methods lim
                        JOIN base_data.instructional_methods im ON im.id = lim.instructional_method_id
                        WHERE lim.lesson_id = $1
                    """, lesson_id)
                    lesson_dict["instructional_methods"] = [dict(r) for r in lim_rows]

                    # Lesson technology integrations
                    lti_rows = await conn.fetch("""
                        SELECT ti.name, ti.description
                        FROM lesson_technology_integrations lti
                        JOIN base_data.technology_integrations ti ON ti.id = lti.technology_integration_id
                        WHERE lti.lesson_id = $1
                    """, lesson_id)
                    lesson_dict["technology_integrations"] = [dict(r) for r in lti_rows]

                    lessons.append(lesson_dict)

                module_dict["lessons"] = lessons

                # Module instructional methods
                mim_rows = await conn.fetch("""
                    SELECT im.name, im.description
                    FROM modules_instructional_methods mim
                    JOIN base_data.instructional_methods im ON im.id = mim.instructional_method_id
                    WHERE mim.module_id = $1
                """, module_id)
                module_dict["instructional_methods"] = [dict(r) for r in mim_rows]

                # Module digital tools (free text)
                mdt_row = await conn.fetchrow("""
                    SELECT digital_tools FROM module_digital_tools WHERE module_id = $1
                """, module_id)
                module_dict["digital_tools"] = mdt_row["digital_tools"] if mdt_row else ""

                # Primary/Secondary materials
                mpm_row = await conn.fetchrow("""
                    SELECT primary_materials FROM module_primary_materials WHERE module_id = $1
                """, module_id)
                msm_row = await conn.fetchrow("""
                    SELECT secondary_materials FROM module_secondary_materials WHERE module_id = $1
                """, module_id)
                module_dict["primary_materials"] = mpm_row["primary_materials"] if mpm_row else ""
                module_dict["secondary_materials"] = msm_row["secondary_materials"] if msm_row else ""

                # Assessment types
                mat_rows = await conn.fetch("""
                    SELECT at.name FROM modules_assessment_types mat
                    JOIN base_data.assessment_types at ON at.id = mat.assessment_type_id
                    WHERE mat.module_id = $1
                """, module_id)
                module_dict["assessment_types"] = [r["name"] for r in mat_rows]

                # Training references
                tr_rows = await conn.fetch("""
                    SELECT definition FROM training_references WHERE module_id = $1
                """, module_id)
                module_dict["references"] = [r["definition"] for r in tr_rows]

                # Contents for this module and its lessons (including video/media links)
                content_rows = await conn.fetch("""
                    SELECT c.id, c.name, c.file_type, c.level, c.link, c.description, c.time_to_read_minutes, c.lesson_id
                    FROM contents c
                    WHERE (c.module_id = $1 OR c.lesson_id IN (SELECT id FROM lessons WHERE module_id = $1))
                      AND (c.status = 'ACCEPTED' OR (c.link IS NOT NULL AND length(trim(c.link)) > 0))
                """, module_id)
                module_dict["accepted_contents"] = [dict(r) for r in content_rows]

                modules.append(module_dict)

            return modules

    # ==================== Audience Profile ====================

    async def get_audience_profile(self, training_id: str) -> dict:
        """Get audience profile with resolved base_data references."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT ap.*, 
                       el.name as education_level, el.description as education_level_desc,
                       l.name as language_name, l.code as language_code, l.alternate_names as language_alternates,
                       ll.name as learner_level, ll.description as learner_level_desc,
                       we.name as work_experience, we.description as work_experience_desc
                FROM audience_profiles ap
                LEFT JOIN base_data.education_levels el ON el.id = ap.education_level_id
                LEFT JOIN base_data.languages l ON l.id = ap.language_id
                LEFT JOIN base_data.learner_levels ll ON ll.id = ap.learner_level_id
                LEFT JOIN base_data.work_experiences we ON we.id = ap.work_experience_id
                WHERE ap.training_id = $1
            """, training_id)

            if not row:
                return {}

            result = dict(row)

            # Specific courses & prerequisites
            courses_rows = await conn.fetch("""
                SELECT specific_courses FROM specific_courses WHERE audience_profile_id = $1
            """, result["id"])
            prereq_rows = await conn.fetch("""
                SELECT specific_prerequisites FROM specific_prerequisites WHERE audience_profile_id = $1
            """, result["id"])

            result["specific_courses"] = [r["specific_courses"] for r in courses_rows]
            result["specific_prerequisites"] = [r["specific_prerequisites"] for r in prereq_rows]

            return result

    # ==================== Learner Profile ====================

    async def get_learner_profile(self, learner_id: str) -> dict:
        """
        Get learner (trainee) profile with joined user, role, and lookup data.

        Explicitly selects trainee columns to avoid column shadowing issues
        that arise from SELECT tr.* when JOINed with users (both have first_name, last_name).

        learner_id may be trainee.id or user.id — tries trainee.id first.
        Returns empty dict if not found.
        """
        TRAINEE_SELECT = """
            SELECT
                tr.id,
                tr.training_id,
                tr.user_id,
                tr.first_name,
                tr.last_name,
                tr.middle_name,
                tr.email,
                tr.contact_phone,
                tr.gender,
                tr.date_of_birth,
                tr.field_of_study,
                tr.employment_status,
                tr.marital_status,
                tr.has_smart_phone,
                tr.has_training_experience,
                tr.training_experience_description,
                tr.number_of_children,
                tr.woreda,
                tr.house_number,
                tr.cohort_id,
                tr.is_self_registered,
                tr.created_at,
                tr.updated_at,
                -- User account fields
                u.username,
                u.email          AS user_email,
                u.phone_number,
                u.profile_picture_url,
                u.is_active,
                -- Role
                r.name           AS role_name,
                -- Lookup denormalisations
                al.name          AS academic_level,
                al.code          AS academic_level_code,
                l.name           AS language_name,
                l.code           AS language_code,
                c.name           AS city_name,
                z.name           AS zone_name
            FROM trainees tr
            LEFT JOIN users u                   ON u.id  = tr.user_id
            LEFT JOIN roles r                   ON r.id  = u.role_id
            LEFT JOIN base_data.academic_levels al ON al.id = tr.academic_level_id
            LEFT JOIN base_data.languages l     ON l.id  = tr.language_id
            LEFT JOIN base_data.cities c        ON c.id  = tr.city_id
            LEFT JOIN base_data.zones z         ON z.id  = tr.zone_id
        """

        async with self._pool.acquire() as conn:
            # 1. Try trainee primary key
            row = await conn.fetchrow(TRAINEE_SELECT + " WHERE tr.id = $1", learner_id)
            if row:
                return dict(row)

            # 2. Try user.id → trainee lookup
            row = await conn.fetchrow(TRAINEE_SELECT + " WHERE tr.user_id = $1", learner_id)
            if row:
                return dict(row)

            return {}

    async def get_accepted_content(self, training_id: str) -> list[dict]:
        """Get all ACCEPTED content for a training (for RAG indexing), enriched with module & lesson learning content."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT c.*, 
                       m.name as module_name, 
                       m.description as module_description,
                       m.key_concepts as module_key_concepts,
                       m.teaching_strategy as module_teaching_strategy,
                       m.module_order,
                       l.name as lesson_name,
                       l.description as lesson_description,
                       l.objective as lesson_objective
                FROM contents c
                JOIN modules m ON m.id = c.module_id
                LEFT JOIN lessons l ON l.id = c.lesson_id
                WHERE m.training_id = $1::uuid AND c.status = 'ACCEPTED'
                ORDER BY m.module_order, c.level, c.created_at
            """, training_id)
            return [dict(r) for r in rows]

    # ==================== Save Generated Curriculum ====================

    async def save_generated_curriculum(self, training_id: str, curriculum: dict) -> str:
        """
        Save generated curriculum to ai_generated_curricula (AI-service-owned table).
        Idempotent: returns existing ID if an identical curriculum exists for this training.
        """
        curr_json = json.dumps(curriculum)
        async with self._pool.acquire() as conn:
            existing = await conn.fetchrow("""
                SELECT id FROM ai_generated_curricula
                WHERE training_id = $1 AND curriculum_json = $2::jsonb
            """, training_id, curr_json)
            if existing:
                return str(existing["id"])

            row = await conn.fetchrow("""
                INSERT INTO ai_generated_curricula (training_id, curriculum_json)
                VALUES ($1, $2::jsonb)
                RETURNING id
            """, training_id, curr_json)
            return str(row["id"])

    async def get_latest_curriculum(self, training_id: str) -> Optional[dict]:
        """
        Retrieve the most recently generated curriculum for a training.
        Returns None if no curriculum has been generated yet.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT curriculum_json, generated_at, id
                FROM ai_generated_curricula
                WHERE training_id = $1
                ORDER BY generated_at DESC
                LIMIT 1
            """, training_id)
            if not row:
                return None
            raw_json = row["curriculum_json"]
            data = json.loads(raw_json) if isinstance(raw_json, str) else dict(raw_json)
            data.setdefault("metadata", {})
            data["metadata"]["curriculum_db_id"] = str(row["id"])
            data["metadata"]["generated_at_db"] = str(row["generated_at"])
            return data

    async def is_learner_enrolled(self, learner_id: str, training_id: str) -> bool:
        """Check if a trainee is enrolled in the specified training."""
        if self._pool is None:
            return False
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 1 FROM trainees WHERE id = $1 AND training_id = $2
            """, learner_id, training_id)
            return row is not None

    async def save_custom_training(
        self,
        training_id: str,
        title: str,
        rationale: str,
        scope: str,
        duration_hours: float,
        delivery_method: str = "BLENDED"
    ) -> None:
        """Create a training record in the trainings table for a custom curriculum generated from scratch."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO trainings (id, title, rationale, scope, duration, duration_type, delivery_method, is_deleted)
                VALUES ($1::uuid, $2, $3, $4, $5, 'HOURS', $6, false)
                ON CONFLICT (id) DO NOTHING
            """, training_id, title, rationale, scope, duration_hours, delivery_method)

    async def get_all_recent_curricula(self, limit: int = 25) -> list[dict]:
        """
        Return the most recently generated curricula across all trainings, newest first.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id,
                    training_id,
                    generated_at,
                    jsonb_array_length(COALESCE(curriculum_json->'modules', '[]'::jsonb)) AS module_count,
                    curriculum_json->>'training_title'                                     AS training_title,
                    COALESCE(curriculum_json->'metadata'->>'mode', 'db_training')          AS mode,
                    curriculum_json->'validation_report'                                   AS validation_report
                FROM ai_generated_curricula
                ORDER BY generated_at DESC
                LIMIT $1
            """, limit)

            def _safe_json(v):

                if not v:
                    return {}
                if isinstance(v, dict):
                    return v
                try:
                    return json.loads(v)
                except Exception:
                    return {}

            return [
                {
                    "curriculum_db_id": str(r["id"]),
                    "training_id": str(r["training_id"]),
                    "generated_at": str(r["generated_at"]),
                    "module_count": r["module_count"],
                    "training_title": r["training_title"] or "Untitled Curriculum",
                    "mode": r["mode"],
                    "validation_report": _safe_json(r["validation_report"]),
                }
                for r in rows
            ]

    async def get_curriculum_by_db_id(self, curriculum_db_id: str) -> Optional[dict]:
        """Retrieve a specific curriculum by its ai_generated_curricula UUID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT curriculum_json, generated_at, id, training_id
                FROM ai_generated_curricula
                WHERE id = $1::uuid
            """, curriculum_db_id)
            if not row:
                return None
            raw_json = row["curriculum_json"]
            data = json.loads(raw_json) if isinstance(raw_json, str) else dict(raw_json)
            data.setdefault("metadata", {})
            data["metadata"]["curriculum_db_id"] = str(row["id"])
            data["metadata"]["generated_at_db"] = str(row["generated_at"])
            data["metadata"]["from_cache"] = True
            return data

    async def get_curriculum_history(self, training_id: str) -> list[dict]:
        """Return all generated curriculum versions for a training, newest first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id,
                    generated_at,
                    jsonb_array_length(COALESCE(curriculum_json->'modules', '[]'::jsonb)) AS module_count,
                    curriculum_json->>'training_title'                                     AS training_title,
                    curriculum_json->'validation_report'                                   AS validation_report
                FROM ai_generated_curricula
                WHERE training_id = $1::uuid
                ORDER BY generated_at DESC
            """, training_id)
            def _safe_json(v):
                if not v:
                    return {}
                if isinstance(v, dict):
                    return v
                try:
                    return json.loads(v)
                except Exception:
                    return {}

            return [
                {
                    "curriculum_db_id": str(r["id"]),
                    "generated_at": str(r["generated_at"]),
                    "module_count": r["module_count"],
                    "training_title": r["training_title"],
                    "validation_report": _safe_json(r["validation_report"]),
                }
                for r in rows
            ]

    # ==================== RAG Indexing Helpers ====================

    async def get_all_trainings(self) -> list[dict]:
        """Get all active trainings (id, title) for batch indexing."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, title, professional_background, delivery_method
                FROM trainings
                WHERE is_deleted = false
                ORDER BY created_at DESC
            """)
            return [dict(r) for r in rows]

    async def delete_training_chunks(self, training_id: str) -> int:
        """Delete existing chunks for a training before a full clean re-index."""
        async with self._pool.acquire() as conn:
            res = await conn.execute("""
                DELETE FROM ai_content_chunks c
                USING modules m
                WHERE c.module_id = m.id AND m.training_id = $1::uuid
            """, training_id)
            # res format: "DELETE <count>"
            try:
                return int(res.split()[-1])
            except Exception:
                return 0

    async def count_training_chunks(self, training_id: str) -> int:
        """Count total chunks stored in DB for a specific training."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(*) as n FROM ai_content_chunks c
                JOIN modules m ON m.id = c.module_id
                WHERE m.training_id = $1::uuid
            """, training_id)
            return int(row["n"]) if row else 0

    # ==================== Learner Progress Evidence (Teammate 4) ====================

    async def _resolve_trainee(self, learner_id: str, training_id: str) -> Optional[dict]:
        """Resolve a learner_id (trainee.id or user.id) to a trainee row in a training."""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT id, cohort_id FROM trainees
                WHERE (id = $1::uuid OR user_id = $1::uuid) AND training_id = $2::uuid
                LIMIT 1
            """, learner_id, training_id)

    async def get_learner_progress(self, learner_id: str, training_id: str) -> dict:
        """
        Aggregate real learner evidence from TSP for personalization:
        - Attendance: sessions attended vs. recorded (attendances + sessions).
        - Session timeline: last attended session and next unattended session in the cohort.
        - Assessment performance: weight-normalized percentage per assessment
          (assessment_answers.score / assessment_entries.weight), plus the weakest area.

        Returns {} when the learner has no evidence in TSP — callers must treat
        that as "no evidence available", never fabricate progress.
        """
        if self._pool is None:
            return {}
        trainee = await self._resolve_trainee(learner_id, training_id)
        if not trainee:
            return {}
        trainee_id = trainee["id"]

        async with self._pool.acquire() as conn:
            att = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE a.is_present) AS attended,
                    COUNT(*) AS recorded
                FROM attendances a
                WHERE a.trainee_id = $1
            """, trainee_id)

            timeline = await conn.fetch("""
                SELECT s.id, s.name, s.start_date, s.status,
                       COALESCE(a.is_present, FALSE) AS is_present,
                       (a.id IS NOT NULL) AS has_record
                FROM sessions s
                LEFT JOIN attendances a
                       ON a.session_id = s.id AND a.trainee_id = $1
                WHERE s.cohort_id = $2
                ORDER BY s.start_date
            """, trainee_id, trainee["cohort_id"]) if trainee["cohort_id"] else []

            assessments = await conn.fetch("""
                SELECT ass.name AS assessment_name,
                       ass.assessment_type,
                       ROUND((SUM(aa.score) / NULLIF(SUM(ae.weight), 0))::numeric * 100, 1) AS pct,
                       COUNT(aa.id) AS answers
                FROM assessment_answers aa
                JOIN assessment_entries ae ON ae.id = aa.assessment_entry_id
                JOIN assessment_sections sec ON sec.id = ae.section_id
                JOIN assessments ass ON ass.id = sec.assessment_id
                WHERE aa.trainee_id = $1 AND aa.score IS NOT NULL
                GROUP BY ass.id, ass.name, ass.assessment_type
                ORDER BY pct ASC NULLS LAST
            """, trainee_id)

        attended = int(att["attended"]) if att else 0
        recorded = int(att["recorded"]) if att else 0

        last_attended = None
        next_session = None
        for s in timeline:
            if s["is_present"]:
                last_attended = {"name": s["name"], "start_date": str(s["start_date"]), "status": s["status"]}
            elif next_session is None:
                next_session = {"name": s["name"], "start_date": str(s["start_date"]), "status": s["status"]}

        assessment_results = [
            {
                "assessment_name": a["assessment_name"],
                "assessment_type": a["assessment_type"],
                "score_pct": float(a["pct"]) if a["pct"] is not None else None,
                "answers": int(a["answers"]),
            }
            for a in assessments
        ]
        scored = [a for a in assessment_results if a["score_pct"] is not None]
        overall_pct = round(sum(a["score_pct"] for a in scored) / len(scored), 1) if scored else None
        weakest = next((a for a in scored if a["answers"] >= 3), None)

        if not (recorded or assessment_results):
            return {}

        return {
            "trainee_id": str(trainee_id),
            "attendance": {
                "attended": attended,
                "recorded": recorded,
                "rate": round(attended / recorded, 2) if recorded else None,
            },
            "last_attended_session": last_attended,
            "next_session": next_session,
            "assessment_results": assessment_results,
            "overall_assessment_pct": overall_pct,
            "weakest_assessment": weakest,
        }

    async def find_diverse_learners(self, training_id: str, limit: int = 3) -> List[dict]:
        """
        Pick learners in a training with real TSP evidence and (where possible)
        distinct academic levels — used by the personalization evaluation.
        """
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT ON (al.name)
                       t.id, t.first_name, t.last_name,
                       al.name AS academic_level,
                       t.employment_status, t.has_training_experience,
                       COUNT(aa.id) OVER (PARTITION BY t.id) AS answers
                FROM trainees t
                LEFT JOIN base_data.academic_levels al ON al.id = t.academic_level_id
                JOIN assessment_answers aa ON aa.trainee_id = t.id
                WHERE t.training_id = $1::uuid
                ORDER BY al.name, t.has_training_experience DESC
                LIMIT $2
            """, training_id, limit)
            return [dict(r) for r in rows]

    # ==================== Copilot Session Persistence (Teammate 4) ====================

    async def save_copilot_turn(
        self,
        session_id: str,
        training_id: str,
        learner_id: Optional[str],
        role: str,
        content: str,
        guardrail_triggered: bool = False,
    ) -> bool:
        """
        Persist one conversation turn to ai_copilot_sessions. Best-effort:
        returns False (never raises) if the table is missing or the write fails,
        so the copilot keeps working with in-memory sessions only.
        """
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ai_copilot_sessions
                        (session_id, training_id, learner_id, role, content, guardrail_triggered)
                    VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6)
                """, session_id, training_id, learner_id, role, content, guardrail_triggered)
            return True
        except Exception:
            return False

    async def get_copilot_session_history(self, session_id: str, limit: int = 20) -> List[dict]:
        """Load a session's turns (oldest first) from ai_copilot_sessions. Best-effort."""
        if self._pool is None:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT role, content FROM ai_copilot_sessions
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, session_id, limit)
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        except Exception:
            return []

    async def get_recent_learner_interactions(self, learner_id: str, limit: int = 6) -> List[dict]:
        """Most recent copilot turns for a learner across sessions (profile context)."""
        if self._pool is None:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT role, content, session_id, created_at
                    FROM ai_copilot_sessions
                    WHERE learner_id = $1::uuid AND guardrail_triggered = FALSE
                    ORDER BY created_at DESC
                    LIMIT $2
                """, learner_id, limit)
            return [
                {"role": r["role"], "content": r["content"], "session_id": r["session_id"]}
                for r in reversed(rows)
            ]
        except Exception:
            return []

    async def delete_training_chunks(self, training_id: str) -> int:
        """Delete all chunks for a training from ai_content_chunks."""
        if self._pool is None:
            return 0
        try:
            async with self._pool.acquire() as conn:
                res = await conn.execute("""
                    DELETE FROM ai_content_chunks
                    WHERE content_id IN (
                        SELECT c.id FROM contents c
                        JOIN modules m ON m.id = c.module_id
                        WHERE m.training_id = $1::uuid
                    )
                """, training_id)
                # Parse 'DELETE <count>'
                parts = res.split()
                return int(parts[1]) if len(parts) > 1 else 0
        except Exception as e:
            print(f"[Warning] Failed to delete chunks for training {training_id}: {e}")
            return 0

    async def count_training_chunks(self, training_id: str) -> int:
        """Count total chunks stored for a training."""
        if self._pool is None:
            return 0
        try:
            async with self._pool.acquire() as conn:
                val = await conn.fetchval("""
                    SELECT count(*) FROM ai_content_chunks
                    WHERE content_id IN (
                        SELECT c.id FROM contents c
                        JOIN modules m ON m.id = c.module_id
                        WHERE m.training_id = $1::uuid
                    )
                """, training_id)
                return int(val or 0)
        except Exception:
            return 0



# Singleton instance for FastAPI lifespan
_tsp_client: Optional[TSPClient] = None


async def get_tsp_client() -> TSPClient:
    global _tsp_client
    if _tsp_client is None:
        _tsp_client = TSPClient()
        await _tsp_client.connect()
    return _tsp_client


async def close_tsp_client() -> None:
    global _tsp_client
    if _tsp_client:
        await _tsp_client.close()
        _tsp_client = None
