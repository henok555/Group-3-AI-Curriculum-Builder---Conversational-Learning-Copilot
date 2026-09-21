# Copilot Sessions, Evidence-Based Personalization & Next-Activity Engine

**Author**: Abel (Teammate 4 — Copilot & Personalization)
**Grading areas**: RAG/Copilot (12%, shared) + Learner Profiling & Personalization (8%)

This document describes the Teammate 4 layer of the copilot: server-side multi-turn
sessions, personalization grounded in **real learner evidence from TSP** (not just
prompt wording), and a deterministic next-activity recommendation engine.

---

## 1. What was added

| Capability | Where | Assignment requirement it satisfies |
|---|---|---|
| Server-side session store + persistence | `app/session_store.py`, `ai_copilot_sessions` table, `app/main.py` | "Maintain multi-turn context", "Previous copilot interactions" in learner profile |
| Learner progress evidence aggregation | `TSPClient.get_learner_progress()` | "Personalization must be based on actual learner evidence from TSP" |
| Performance-adaptive support | `derive_performance_adaptation()` in `app/main.py` | "Adapt support based on learner performance", remedial support |
| Deterministic next-activity recommendation with reason | `recommend_next_activity()` in `app/main.py` | "Recommend the next learning activity" + "Explain why an activity is recommended" |
| Personalization/multi-turn/safety evaluation | `scripts/evaluate_personalization.py` → `docs/evaluation_personalization.md` | Evaluation requirements (personalization, copilot quality, safety) |

---

## 2. Multi-turn sessions

### Design

```
CopilotRequest.session_id (optional)
        │
        ▼
┌─ in-memory SessionStore (app/session_store.py) ── fast path, 20-turn window
│       │ miss on cold start
│       ▼
└─ ai_copilot_sessions table ── durable, hydrates memory after a restart
```

- A response always returns a `session_id`. The client passes it back to continue
  the conversation — **no need to re-send conversation history** (the old
  `conversation_history` field still works as a fallback for legacy clients).
- Every exchange (learner question + copilot answer, including guardrail
  refusals) is appended to the in-memory store and persisted **best-effort** to
  `ai_copilot_sessions`. If the table is missing or the write fails, the copilot
  keeps working memory-only — persistence never breaks answering.
- On a cold start (service restart), a known `session_id` is re-hydrated from the
  table, so conversations survive restarts.

### Table (see `docs/db_migrations.sql`)

```sql
ai_copilot_sessions (
    id UUID PK, session_id VARCHAR(64), training_id UUID, learner_id UUID,
    role VARCHAR(16) CHECK (role IN ('learner','copilot')),
    content TEXT, guardrail_triggered BOOLEAN, created_at TIMESTAMP
)
```

One row per turn; indexed by `(session_id, created_at)` and
`(learner_id, created_at)`. The learner index powers
`TSPClient.get_recent_learner_interactions()` — the learner's previous copilot
interactions across sessions, part of the required learner profile.

---

## 3. Evidence-based personalization

Personalization previously used **demographics only** (academic level, employment
status, prior experience → 3 pedagogical tiers). The assignment requires more:

> "Personalization must be based on actual learner evidence from TSP, not only
> prompt wording. Teams must show how learner data, progress, assessment results,
> and competency information are passed from the TSP backend to the AI service."

### TSP evidence used (`TSPClient.get_learner_progress`)

| TSP table | Evidence extracted |
|---|---|
| `attendances` + `sessions` | sessions attended / recorded, attendance rate, last attended session, next unattended session in the cohort schedule |
| `assessment_answers` + `assessment_entries` + `assessment_sections` + `assessments` | **weight-normalized** score per assessment (`Σ score / Σ weight`), overall %, weakest assessment area |
| `trainees` | resolves `learner_id` (trainee id **or** user id) within the training, cohort membership |

If the learner has **no records**, the function returns `{}` and every downstream
consumer treats it as "no evidence" — the system never invents progress
(assignment: *"Missing TSP information does not result in fabricated facts"*).

### Performance adaptation (`derive_performance_adaptation`)

| Level | Trigger (from real records) | Effect on the answer |
|---|---|---|
| `struggling` | overall score < 50% **or** attendance rate < 60% | remedial: re-explain prerequisites, simplest framing, encouragement, point back to the weakest area |
| `excelling` | overall score ≥ 80% **and** attendance ≥ 90% | skip basics, add depth/edge cases, peer-level framing, stretch work |
| `on_track` | any other learner with evidence | reinforce, tier-level answers, steady progression |
| `no_evidence` | no attendance/assessment rows in TSP | profile-only personalization, explicitly no performance assumptions |

This is layered **on top of** the demographic tier (Beginner / Intermediate /
Advanced), so two learners with the same degree get different support if their
actual performance differs — the personalization is driven by data, not wording.

Both the evidence summary and the adaptation directive are injected into the
system prompt (`PERFORMANCE-BASED ADAPTATION` block) and the user prompt
(`LEARNER PROGRESS EVIDENCE` block), and the response reports them in a
structured `personalization` field so the demo can show *why* answers differ.

---

## 4. Next-activity recommendation — deterministic, with a "why"

`recommend_next_activity()` is computed **in code from TSP records** and passed
to the LLM with the instruction "do not change it" — the recommendation can never
be hallucinated. Decision order:

1. **Struggling + known weakest area** → review the materials covered by that
   assessment; reason cites the actual score.
2. **Unattended session remains in the cohort schedule** → attend it; reason
   cites the schedule date and the last session attended.
3. **Excelling, schedule complete** → advanced assignment / peer coaching;
   reason cites the real overall score.
4. **Schedule complete, not excelling** → consolidate the last session's material.
5. **No TSP evidence** → tier-based suggestion, with an honest reason that no
   records were found.

The result is returned as `recommended_next_activity: {activity, reason}` in the
API response and woven into the answer text.

---

## 5. API changes (`POST /copilot/message`)

Request (all new fields optional — fully backward compatible):

```json
{
  "training_id": "ea7953f9-...",
  "learner_id": "855be580-...",
  "question": "What do the financial literacy materials cover?",
  "session_id": "992b541e-..."   // returned by the previous response
}
```

Response additions:

```json
{
  "session_id": "992b541e-...",
  "personalization": {
    "tier": "Intermediate / Applied",
    "performance_level": "on_track",
    "evidence_summary": "Learner evidence from TSP: attended 4/4 recorded sessions (100%); overall assessment score 71.4%; ..."
  },
  "recommended_next_activity": {
    "activity": "Attend \"Financial Literacy Training - Session 3\".",
    "reason": "TSP shows this is the next session in your cohort schedule (2025-05-24), following \"Digital Literacy Training - Session 2\" which you already attended."
  }
}
```

Guardrail behavior is unchanged (2-layer injection check, enrollment check,
honest refusal when retrieval finds nothing) — guardrail exchanges are also
recorded in the session so multi-turn context stays faithful.

---

## 6. Evaluation

`scripts/evaluate_personalization.py` runs the **real pipeline** (live TSP DB,
real retrieval, real LLM) and writes `docs/evaluation_personalization.md`:

1. **Personalization diff** — the same question asked as 3 real learners with
   distinct academic levels; reports tier / performance level / recommendation
   per learner plus pairwise Jaccard similarity between answers (lower = more
   differentiated) and a 1–4 diff score per `docs/evaluation_plan.md`.
2. **Multi-turn coherence** — a follow-up in the same server-side session with
   no client-sent history; verifies the session id is reused, ≥4 turns are stored
   in memory **and** persisted to `ai_copilot_sessions`, and the follow-up is
   answered substantively.
3. **Safety suite** — prompt injection (blocked), unsupported question (honest
   refusal), unauthorized cross-training access with a real learner from another
   training (denied).

Unit tests (no DB/LLM needed): `tests/test_copilot.py` — 18 tests covering the
performance-adaptation thresholds, recommendation decision order, session store
(round-trip, isolation, window trimming, hydration), prompt assembly, and
injection-pattern regression.

---

## 7. Known limitations

- The in-memory session store is per-process; with multiple uvicorn workers a
  session sticks only via the DB hydration path (acceptable for the demo's
  single-worker deployment).
- Attendance evidence relies on `attendances` rows existing; trainings that never
  recorded attendance yield `no_evidence` even for active learners.
- Assessment percentages are weight-normalized across **answered** questions
  only; unanswered questions do not count against the learner.
- Competency-gap detection is approximated by the weakest assessment area — TSP
  has no explicit per-competency scoring to draw from (see `docs/limitations.md`).
