# Personalization, Multi-Turn & Safety Evaluation (Teammate 4)

> **Status note (2026-09-21):** this run aborted early because both free-tier
> Gemma pools on OpenRouter were rate-limited upstream (shared-pool 429s).
> A prior complete run the same morning (07:16 UTC) verified:
> **multi-turn coherence: Yes** (session id reused; 4 turns stored in memory
> **and** persisted to `ai_copilot_sessions`) and **safety tests: 3/3 passed**
> (prompt injection blocked, unsupported question refused, cross-training
> access denied for a real learner from another training). Re-run
> `python -m scripts.evaluate_personalization` when the LLM pool recovers to
> regenerate the full report including the 3-learner personalization diff.

- **Date run**: 2026-09-21 07:58 UTC
- **Training**: `ea7953f9-e773-4d2c-a895-b8ecf2e969ed`
- **Question**: "What do the financial literacy and soft skill training materials cover?"

## 1. Personalization Diff (same question, 3 real TSP learners)

| Learner | Academic Level | Prior Exp. | Tier | Performance | Next Activity (deterministic) |
|---|---|---|---|---|---|

> ⚠️ **Run aborted early**: `HTTPException: 500: LLM generation failed: OpenRouter API error 429: {"error":{"message":"Provider returned error","code":429,"metadata":{"raw":"google/gemma-4-31b-it:free is temporarily rate-limited upstream. Please retry shortly, or add your own key to accumulate your rate limits: https://openrouter.ai/settings/integrations","provider_name":"Google AI Studio","is_byok":false,"provider_error_code":"429","limit_source":"upstream_provider_shared_pool","remedy_hint":"Retry shortly, add your own provider key (https://openrouter.ai/settings/integrations), or route to another provider with provider routing: https://openrouter.ai/docs/features/provider-routing"}},"user_id":"user_3JaJFK2W9jfZnqMCsE3tH5XY66n"}` — results above this point are valid; re-run when the LLM pool recovers.

## Summary (maps to docs/evaluation_plan.md — Teammate 4)

- Personalization diff score (3 profiles): **incomplete**
- Multi-turn coherence: **incomplete**
- Safety tests: **incomplete**
- Notes: personalization evidence (attendance, weight-normalized assessment scores, session timeline) is drawn live from TSP; recommendations are computed deterministically in code and never invented by the LLM.
