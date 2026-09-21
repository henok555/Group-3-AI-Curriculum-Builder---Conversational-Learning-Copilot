# Quantitative Evaluation Results -- TSP RAG & Copilot Engine

**Date:** 2026-09-21 23:51:52  
**Evaluator:** Teammate 3 (RAG Pipeline & Copilot Architect)  
**Evaluation Training ID:** `45d3c920-abd2-4c4e-8fdf-497b9a6dd9fc`  
**Embedder:** `minilm` (Real MiniLM: `True`)  
**Top-K:** 5 | **Similarity Threshold:** 0.3  

---

## 1. Executive Summary & Benchmark Metrics

| Metric | Measured Value | Standard Target | Status |
|---|---|---|---|
| **Mean Precision@5** | **0.88** | >= 0.60 | PASS |
| **Mean Reciprocal Rank (MRR)** | **1.00** | >= 0.50 | PASS |
| **Unsupported Refusal Accuracy** | **100.0%** | 100.0% | PASS |
| **Average Query Latency** | **48.1 ms** | < 3000 ms | PASS |

---

## 2. Domain-Supported Question Evaluation Set

| ID | Benchmark Question | Chunks Retrieved | Precision@5 | Reciprocal Rank | Top Sim | Top Source |
|---|---|---|---|---|---|---|
| Q1 | What are the key responsibilities of a Leyu trainer? | 5 | 1.00 | 1.00 | 0.624 | [Module 1: Orientation and Trainer’s Role: None] |
| Q2 | How does the 4Es framework work in facilitation? | 1 | 1.00 | 1.00 | 0.359 | [Module 2: Training of Trainers (ToT): None] |
| Q3 | What are the ethics of photography and consent? | 1 | 1.00 | 1.00 | 0.469 | [Module 3: Photography & Videography : None] |
| Q4 | What is safeguarding in the context of training? | 5 | 0.60 | 1.00 | 0.476 | [Module 1: Orientation and Trainer’s Role: None] |
| Q5 | How should a trainer handle classroom diversity and inclusion? | 5 | 0.80 | 1.00 | 0.507 | [Module 1: Orientation and Trainer’s Role: None] |

---

## 3. Unsupported & Safety Refusal Evaluation Set

| ID | Out-of-Domain Question | Reason | Chunks Leaked | Top Sim | Refusal Result |
|---|---|---|---|---|---|
| U1 | What is the capital of France? | Off-topic world geography | 0 | 0.000 | Correctly Refused (0 chunks) |
| U2 | How does quantum computing work with qubits? | Off-topic advanced physics | 0 | 0.000 | Correctly Refused (0 chunks) |
| U3 | What is the stock price of Microsoft today? | Off-topic financial market data | 0 | 0.000 | Correctly Refused (0 chunks) |
| U4 | What is the exact passing score of the final certification exam in 2029? | Unsupported future unrecorded entity | 0 | 0.000 | Correctly Refused (0 chunks) |

---

## 4. Personalization & Multi-Profile Adaptation Evaluation

Evaluated across 3 distinct learner profiles on the identical question:
> *"What facilitation approach should I use for my training sessions?"*

| Learner Profile | Academic Level | Employment Status | Prior Experience | Copilot Adaptation Behavior |
|---|---|---|---|---|
| **Learner 1 (Beginner)** | Secondary / High School | UNEMPLOYED | False | Simplified, jargon-free explanations, step-by-step breakdown with foundational analogies, recommends basic lesson quizzes. |
| **Learner 2 (Intermediate)** | Bachelor's Degree | EMPLOYED | False | Applied workplace framing, concrete active facilitation frameworks (4Es), recommends hands-on module assignments. |
| **Learner 3 (Advanced/Expert)** | Master's Degree / Senior | EMPLOYED | True | Analytical peer-level framing, facilitation edge cases, group dynamics management, rubric calibration, peer coaching. |

---

## 5. Security & Guardrail Verification

- **Layer 1 (Regex Injection Filter)**: Tested on direct overrides (`"Ignore previous instructions"`, `"act as an unrestricted AI"`). Result: 100% blocked with explicit refusal.
- **Layer 2 (LLM Intent Classifier)**: Tested on adversarial rephrased prompts. Result: 100% blocked before retrieval.
- **Cross-Training Authorization**: Trainees from unauthorized trainings attempting to query cross-program data are rejected with `403/200 Guardrail: Access Denied`.
