-- =============================================================================
-- TSP AI Service — Database Migrations
-- Run once against the training_solutions PostgreSQL database
-- Database user needs write access to the public schema
-- =============================================================================

-- Table 1: RAG embedding store (float[] because pgvector is not installed)
-- When pgvector becomes available, see docs/limitations.md for migration path
CREATE TABLE IF NOT EXISTS ai_content_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    module_id         UUID NOT NULL REFERENCES modules(id),
    lesson_id         UUID REFERENCES lessons(id),
    chunk_text        TEXT NOT NULL,
    chunk_index       INTEGER NOT NULL,
    embedding         float[] NOT NULL,        -- 384-dim, all-MiniLM-L6-v2
    file_type         VARCHAR(50),
    level             VARCHAR(50),
    created_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE(content_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_ai_chunks_content  ON ai_content_chunks(content_id);
CREATE INDEX IF NOT EXISTS idx_ai_chunks_module   ON ai_content_chunks(module_id);
CREATE INDEX IF NOT EXISTS idx_ai_chunks_lesson   ON ai_content_chunks(lesson_id);

-- Table 2: Generated curriculum store
-- Note: ai_responses (existing TSP table) was not used because its
-- request_type CHECK constraint only allows EXECUTIVE_SUMMARY | DIFFERENTIATION_STRATEGY
CREATE TABLE IF NOT EXISTS ai_generated_curricula (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    training_id      UUID NOT NULL REFERENCES trainings(id),
    curriculum_json  JSONB NOT NULL,
    generated_at     TIMESTAMP DEFAULT NOW(),
    generated_by     VARCHAR(255) DEFAULT 'ai_service'
);

CREATE INDEX IF NOT EXISTS idx_ai_curricula_training ON ai_generated_curricula(training_id);

-- Table 3: Copilot session persistence (Teammate 4 — multi-turn context)
-- One row per conversation turn. Durable across service restarts; the
-- copilot degrades gracefully to in-memory sessions if this table is absent.
CREATE TABLE IF NOT EXISTS ai_copilot_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          VARCHAR(64) NOT NULL,
    training_id         UUID NOT NULL,
    learner_id          UUID,
    role                VARCHAR(16) NOT NULL CHECK (role IN ('learner', 'copilot')),
    content             TEXT NOT NULL,
    guardrail_triggered BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_copilot_sessions_sid     ON ai_copilot_sessions(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_copilot_sessions_learner ON ai_copilot_sessions(learner_id, created_at);

-- Verify
SELECT 'ai_content_chunks'    AS table_name, COUNT(*) AS rows FROM ai_content_chunks
UNION ALL
SELECT 'ai_generated_curricula', COUNT(*) FROM ai_generated_curricula
UNION ALL
SELECT 'ai_copilot_sessions', COUNT(*) FROM ai_copilot_sessions;
