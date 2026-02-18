# Answer Evals — Feature Specification

**Project:** RAG Admin  
**Status:** Draft  
**Version:** 1.0  

---

## 1. Overview

### 1.1 Background

RAG Admin currently supports retrieval evaluation: given a golden set of questions with expected relevant pages, the system fetches chunks from an index and scores retrieval quality using MRR and Recall. This validates that the right context was found, but says nothing about what the LLM did with that context.

Answer evaluation is the complementary layer. It validates the generation step: given what the LLM was shown (retrieved chunks) and what it said (the generated answer), how good was the answer? Specifically:

- Did the LLM stay faithful to the retrieved chunks, or did it hallucinate?
- Did the answer actually address the question asked?

These are independent failure modes. A faithfulness failure means the LLM added information not present in the chunks (hallucination). A relevance failure means the LLM gave a vague or tangential response even though retrieval succeeded.

### 1.2 Goals

- Add answer-quality metrics (faithfulness, answer relevance) to eval runs without disrupting the existing retrieval eval flow.
- Make hallucinations visible and explainable at the claim level — this is the primary explainability feature for consulting clients.
- Store eval results over time so score changes can be tracked across index or configuration iterations.
- Keep the architecture simple and extendable; correctness scoring (requiring reference answers) is explicitly out of scope for v1 but designed for.

### 1.3 Out of Scope (v1)

- Correctness scoring against reference answers (schema supports it; UI and scoring logic deferred).
- Answer playground eval integration (deferred to a follow-on task after core eval run flow is stable).
- Aggregate trend charts across runs (data is stored; UI visualisation deferred).
- Custom judge prompts.

---

## 2. Concepts and Definitions

**Eval mode:** An explicit configuration on an eval run. Either `retrieval_only` or `retrieval_and_answer`. Determines what the run computes and what API calls are made.

**Generation model:** The LLM that generates an answer from the question and retrieved chunks. Configured per eval run.

**Judge model:** A separate LLM that evaluates the generated answer for faithfulness and relevance. Should be a stronger model than the generation model. Configured per eval run.

**Claim:** A single verifiable assertion extracted from the generated answer by the judge model. For example: "Live chat is available 24/7" is one claim. Claims are the atomic unit of faithfulness scoring.

**Faithfulness score:** The fraction of claims in the generated answer that are supported by the retrieved chunks. `supported_claims / total_claims`. Range 0–1.

**Answer relevance score:** A holistic 0–1 score reflecting how well the answer addresses the question. Computed by the judge model in a single pass, not decomposed into sub-scores in v1.

**Supported claim:** A claim for which the judge model finds explicit or strongly implied evidence in the retrieved chunks.

**Unsupported claim:** A claim for which the judge model finds no supporting evidence in the retrieved chunks. This is the hallucination signal.

**Claim breakdown:** The structured array of claim objects (text, support label, source attribution) stored per eval result item.

---

## 3. User Stories

**As a developer iterating on an index**, I want to run a quick retrieval-only eval to check whether chunking changes improved recall, without paying for LLM generation on every iteration.

**As a developer validating the full pipeline**, I want to run a retrieval + answer eval to see faithfulness and relevance scores alongside retrieval metrics in a single run, so I can understand end-to-end quality in one place.

**As a consulting client reviewing pipeline quality**, I want to see exactly which sentences in a generated answer were not supported by the source documents, so I can understand and trust (or challenge) the system's output without needing to read the raw chunks myself.

**As a developer debugging a low-faithfulness answer**, I want to see which specific claims were unsupported and which chunks were retrieved, so I can determine whether the failure was a retrieval problem (wrong chunks), a generation problem (LLM ignored good chunks), or a chunking problem (supporting content split across chunk boundaries).

---

## 4. Functional Requirements

### 4.1 Eval Run Creation

**FR-1:** The eval run creation form must include an eval mode selector with two options: `Retrieval Only` and `Retrieval + Answer`. The mode selector is a required field with no default — the user must make an explicit choice.

**FR-2:** When `Retrieval + Answer` is selected, the form must conditionally reveal a configuration section containing: generation model selector and judge model selector. This section must not be visible when `Retrieval Only` is selected.

**FR-3:** Generation model and judge model selectors must draw from the user's existing BYOK provider configurations. No new API key entry is required. If no providers are configured, the selectors must show an empty state with a link to API key settings.

**FR-4:** The judge model selector must default to the strongest available model in the user's configured providers (e.g., GPT-4o over GPT-4o-mini, Claude Sonnet over Claude Haiku). The recommended default must be visually indicated.

**FR-5:** The system prompt used for answer generation must be configurable per eval run in v1 only as a free-text field with a sensible default. Prompt templates are deferred.

**FR-6:** The eval run record must persist: mode, generation model (nullable), judge model (nullable), system prompt (nullable), and all retrieval configuration fields already stored today.

### 4.2 Eval Run Execution

**FR-7:** For `retrieval_only` runs, execution behaviour is unchanged from the current implementation.

**FR-8:** For `retrieval_and_answer` runs, execution must follow this sequential per-item pipeline:

1. Retrieve top-K chunks for the question (existing logic).
2. Score retrieval metrics (existing logic).
3. Generate an answer using the generation model, providing the question and retrieved chunks as context via the configured system prompt.
4. Evaluate the answer using the judge model (see FR-9).
5. Persist answer, faithfulness score, relevance score, and claim breakdown to the result record.

**FR-9:** The judge model evaluation must be a single structured LLM call that returns:

- An array of claims, each with: `text` (string), `label` (enum: `supported` | `unsupported` | `unclear`), and `source` (nullable string — brief description of which chunk supports the claim, if any).
- A relevance score (float 0–1).

The judge call must use a structured output / JSON mode to ensure parseable responses. If the judge call fails or returns malformed output, the result item must be marked with a `judge_error` status and processing must continue to the next item rather than aborting the run.

**FR-10:** Faithfulness score must be computed deterministically from the claim array: `supported_count / total_count`. `unclear` claims are not counted as supported. If the answer contains no claims (empty or trivially short), faithfulness is `null`.

**FR-11:** Eval run execution must be asynchronous. The run record must have a `status` field: `pending`, `running`, `completed`, `failed`. Progress (items completed / total) must be queryable and surfaced in the UI.

**FR-12:** Individual item failures (judge errors, generation errors) must not abort the run. The run completes with a `partial_failure` status if any items failed, alongside a `failed_item_count`.

### 4.3 Results List

**FR-13:** The eval runs list must display Faithfulness and Relevance columns. For `retrieval_only` runs, these columns must display `—` (not blank, not zero).

**FR-14:** The runs list must support filtering by eval mode.

**FR-15:** Score columns must render colour-coded score pills: green (≥0.8), amber (0.5–0.79), red (<0.5).

### 4.4 Run Results View

**FR-16:** The run results view must display summary stat cards for: MRR@5, Recall@5, Faithfulness (avg), Answer Relevance (avg), and item count. Faithfulness and Relevance stat cards must only appear for `retrieval_and_answer` runs.

**FR-17:** The per-question results table must group columns visually into a Retrieval group and an Answer group (using a double-header row). Answer columns must not render for `retrieval_only` runs.

**FR-18:** The results table must support filtering by: All items, Low faithfulness (<0.7), Low relevance (<0.7), Retrieval miss. Filters are mutually exclusive single-select.

**FR-19:** Each row must be clickable and navigate to the item detail view.

### 4.5 Item Detail View

**FR-20:** The item detail view must display: the question, the generated answer, the claim breakdown, and the retrieved chunks — all in a single view without requiring additional navigation.

**FR-21:** The generated answer must be displayed as plain text (no markdown rendering in v1).

**FR-22:** The claim breakdown must render each claim as a card with: a colour-coded status indicator (green = supported, red = unsupported, amber = unclear), the claim text, the status label, and the source attribution string from the judge.

**FR-23:** The claim breakdown must include a summary count header: e.g. "3 supported · 1 unsupported".

**FR-24:** Retrieved chunks must display: rank position, page/source reference, similarity score, and a text excerpt. Top 3 chunks must be shown by default with an expand control for additional chunks.

**FR-25:** The item detail view must include prev/next navigation between result items within the same run, maintaining any active filter from the results table.

**FR-26:** For `retrieval_only` run items, the answer, claim breakdown, and answer score sections must not appear. The view shows only retrieval detail.

### 4.6 Golden Set Schema Extension

**FR-27:** The golden set item schema must gain an optional `reference_answer` text field. This field is nullable and has no effect on v1 answer eval computation. It is added now so the schema supports correctness scoring without a future migration.

**FR-28:** The golden set item edit UI must include the `reference_answer` field as an optional textarea, with a label noting it is used for future correctness scoring.

---

## 5. Data Model

### 5.1 Schema Changes

#### `eval_runs` table — new columns

| Column | Type | Nullable | Description |
|---|---|---|---|
| `mode` | `enum('retrieval_only','retrieval_and_answer')` | No | Explicit eval mode selected at run creation |
| `generation_model_provider` | `varchar(50)` | Yes | Provider key, e.g. `openai`, `anthropic` |
| `generation_model_id` | `varchar(100)` | Yes | Model string, e.g. `gpt-4o-mini` |
| `judge_model_provider` | `varchar(50)` | Yes | Provider key |
| `judge_model_id` | `varchar(100)` | Yes | Model string |
| `system_prompt` | `text` | Yes | Prompt used for generation |
| `status` | `enum('pending','running','completed','partial_failure','failed')` | No | Run execution status |
| `items_completed` | `integer` | No | Count of processed items (for progress) |
| `failed_item_count` | `integer` | No | Count of items with errors |

#### `eval_results` table — new columns

| Column | Type | Nullable | Description |
|---|---|---|---|
| `generated_answer` | `text` | Yes | Full answer text from generation model |
| `faithfulness_score` | `float` | Yes | `supported / total` claims, null if no claims |
| `relevance_score` | `float` | Yes | 0–1 score from judge |
| `claim_breakdown` | `jsonb` | Yes | Array of claim objects (see below) |
| `judge_error` | `text` | Yes | Error message if judge call failed |
| `generation_error` | `text` | Yes | Error message if generation call failed |

#### `golden_set_items` table — new column

| Column | Type | Nullable | Description |
|---|---|---|---|
| `reference_answer` | `text` | Yes | Optional human-written reference answer |

### 5.2 Claim Breakdown JSON Schema

```json
{
  "claims": [
    {
      "text": "Live chat support is available 24/7.",
      "label": "unsupported",
      "source": null
    },
    {
      "text": "Password reset via SMS requires a verified phone number on the account.",
      "label": "supported",
      "source": "Chunk #1 — Account Recovery section, p.4"
    },
    {
      "text": "Manual verification takes 3–5 business days.",
      "label": "supported",
      "source": "Chunk #2 — Identity Verification section, p.4"
    }
  ]
}
```

Label enum values: `supported`, `unsupported`, `unclear`.

---

## 6. Judge LLM Design

### 6.1 Prompt Structure

The judge is called once per eval result item. It receives:

- The original question
- The retrieved chunks (full text, in rank order, with page/source labels)
- The generated answer

It must return structured JSON matching the claim breakdown schema plus a relevance score.

### 6.2 Reference Prompt (v1)

```
You are an expert evaluator assessing the quality of a RAG system's generated answer.

You will be given:
1. A question
2. A set of retrieved source chunks (the only context the system had access to)
3. The generated answer

Your task is to:

STEP 1 — FAITHFULNESS: Decompose the generated answer into individual factual claims. For each claim, determine whether it is supported by the retrieved chunks.
- "supported": The claim is explicitly stated or strongly implied by at least one chunk.
- "unsupported": The claim is not found in any chunk. This includes information that may be generally true but is not present in the provided context.
- "unclear": There is ambiguous or partial evidence.

For supported claims, identify which chunk provides the supporting evidence.

STEP 2 — RELEVANCE: Score how well the answer addresses the question on a scale of 0.0 to 1.0.
- 1.0: The answer directly and completely addresses the question.
- 0.5: The answer partially addresses the question or includes significant irrelevant content.
- 0.0: The answer does not address the question at all.

Return your response as JSON only, with no preamble:

{
  "claims": [
    {
      "text": "<claim text>",
      "label": "supported" | "unsupported" | "unclear",
      "source": "<chunk reference>" | null
    }
  ],
  "relevance_score": <float 0.0–1.0>
}

---

QUESTION:
{question}

RETRIEVED CHUNKS:
{chunks}

GENERATED ANSWER:
{answer}
```

### 6.3 Chunk Formatting for Judge

Chunks are injected into the prompt as:

```
[Chunk #1 | p.4 — Account Recovery | score: 0.94]
Users may initiate password recovery via SMS if a verified phone number exists...

[Chunk #2 | p.4 — Identity Verification | score: 0.88]
For accounts without a recovery phone, users may submit a verification request...
```

### 6.4 Parsing and Validation

The backend must parse the judge response with the following fallback chain:

1. Attempt JSON parse of the raw response.
2. If that fails, attempt to extract a JSON object from a markdown code block.
3. If that fails, log the raw response and mark the item with `judge_error`.

Validate that `claims` is an array, each claim has `text` and `label`, and `relevance_score` is a float. Coerce out-of-range relevance scores to `[0, 1]`.

---

## 7. API Specification

### 7.1 New / Modified Endpoints

#### `POST /api/projects/{project_id}/eval-runs`

Request body gains new optional fields (required when `mode` is `retrieval_and_answer`):

```json
{
  "name": "hybrid-512-baseline",
  "index_id": "uuid",
  "golden_set_id": "uuid",
  "retrieval_config": { ... },
  "mode": "retrieval_and_answer",
  "generation_model": {
    "provider": "openai",
    "model_id": "gpt-4o-mini"
  },
  "judge_model": {
    "provider": "openai",
    "model_id": "gpt-4o"
  },
  "system_prompt": "You are a helpful assistant. Answer the question using only the provided context."
}
```

Validation: if `mode` is `retrieval_and_answer`, both `generation_model` and `judge_model` are required.

#### `GET /api/projects/{project_id}/eval-runs/{run_id}`

Response gains:

```json
{
  "mode": "retrieval_and_answer",
  "generation_model": { ... },
  "judge_model": { ... },
  "status": "completed",
  "items_completed": 42,
  "failed_item_count": 0,
  "summary": {
    "mrr_at_5": 0.81,
    "recall_at_5": 0.88,
    "avg_faithfulness": 0.84,
    "avg_relevance": 0.71
  }
}
```

`avg_faithfulness` and `avg_relevance` are `null` for `retrieval_only` runs.

#### `GET /api/projects/{project_id}/eval-runs/{run_id}/results`

Query params gain: `filter` (enum: `all`, `low_faithfulness`, `low_relevance`, `retrieval_miss`).

Response items gain:

```json
{
  "faithfulness_score": 0.67,
  "relevance_score": 0.91,
  "generated_answer": "...",
  "claim_breakdown": { ... },
  "judge_error": null,
  "generation_error": null
}
```

#### `GET /api/projects/{project_id}/eval-runs/{run_id}/progress`

New endpoint. Returns current execution progress for running jobs.

```json
{
  "status": "running",
  "items_total": 42,
  "items_completed": 17,
  "failed_item_count": 0,
  "started_at": "2026-02-18T14:32:00Z"
}
```

#### `PATCH /api/projects/{project_id}/golden-sets/{set_id}/items/{item_id}`

Existing endpoint gains support for `reference_answer` field.

---

## 8. Frontend Specification

### 8.1 Eval Run Creation Form

The mode selector is implemented as two option cards (not a dropdown) to make the choice visible and its implications clear. Card copy must include a cost/speed signal ("Fast · Cheap" vs "Slower · LLM Cost").

Selecting `Retrieval Only` hides the answer configuration section with a CSS transition. Selecting `Retrieval + Answer` reveals it. The section is visually differentiated with a blue tint border to indicate it is conditional.

The form must disable the submit button and show a validation message if `Retrieval + Answer` is selected but no providers are configured.

### 8.2 Runs List Table

Column order: Name/Index, Mode, Golden Set, MRR@5, Recall@5, Faithfulness, Relevance, Items, Run at, action.

Faithfulness and Relevance column headers include a "New" badge in the initial release.

Runs with `status: running` display an animated progress indicator in the Run at column.

### 8.3 Run Results View

The stat card row shows Faithfulness and Relevance cards only for `retrieval_and_answer` runs. The cards use a purple tint border to visually distinguish them from the retrieval metrics.

The delta indicator (e.g., "↑ 0.09 vs prior run") on stat cards compares against the most recent prior run on the same index in the same mode. If no prior run exists, no delta is shown.

The double-header table grouping uses a thin coloured line between groups rather than background shading to maintain readability at smaller viewports.

### 8.4 Item Detail View

Layout is a two-column grid: left column (wider) contains the generated answer and claim breakdown; right column contains retrieved chunks and the golden set relevant pages summary.

At viewport widths below 1024px, the layout collapses to a single column with chunks moved below the claim breakdown.

The claim breakdown section title includes the aggregate count ("2 supported · 1 unsupported") in badge chips next to the section title rather than in a separate summary row, to reduce vertical space usage.

Chunk cards show the top 3 expanded by default. An "expand" control reveals the remaining chunks inline without navigation.

For `retrieval_only` items, the entire right half of the layout remains but only shows retrieved chunks (no answer or claim breakdown on the left).

---

## 9. Implementation Phases

### Phase 1 — Schema and Backend Foundation

Deliverables: database migrations for all schema changes, the judge LLM service (isolated, unit-testable), updated `POST /eval-runs` endpoint, and the per-item execution pipeline wired into the existing eval run background task.

Acceptance criteria: a `retrieval_and_answer` eval run can be created and executed via API, producing faithfulness scores and claim breakdowns persisted to the database.

### Phase 2 — API Completeness

Deliverables: updated `GET /eval-runs/{id}` with summary scores, updated `GET /results` with filter support, new `GET /progress` endpoint, `PATCH /golden-set-items` for reference_answer.

Acceptance criteria: all frontend data requirements are servable from the API.

### Phase 3 — Frontend: Run Creation

Deliverables: updated run creation form with mode selector and conditional answer config section.

Acceptance criteria: users can create both retrieval-only and retrieval-and-answer runs from the UI. Mode selector, model selectors, and validation all function correctly.

### Phase 4 — Frontend: Results Views

Deliverables: updated runs list with new columns, updated run results view with double-header table and summary cards, item detail view with claim breakdown panel.

Acceptance criteria: all four wireframe screens are implemented and functional. Claim breakdown renders correctly for supported, unsupported, and unclear claims. Filter controls narrow the results table.

### Phase 5 — Polish and Edge Cases

Deliverables: progress indicator on running runs, error states for judge/generation failures, empty state for no providers configured, `reference_answer` field in golden set item editor.

Acceptance criteria: system handles partial failures gracefully; a run with some judge errors still completes and shows results for successful items.

---

## 10. Non-Functional Requirements

**Cost transparency:** The run creation form must display an estimated API call count for `retrieval_and_answer` runs: `(golden set size) × 2 LLM calls` (one generation, one judge). Exact cost estimation is deferred.

**Latency:** Per-item pipeline steps (retrieve → generate → judge) must execute sequentially within a single item but items may be processed in parallel up to a configurable concurrency limit (default: 3) to control API rate limit exposure.

**Idempotency:** Rerunning a failed eval run must not duplicate result records. The run must be restartable from the last successfully completed item.

**Judge model selection guidance:** The UI must recommend using a different (stronger) model as the judge than the generation model. A warning must display if the same model is selected for both roles.

---

## 11. Open Questions

**OQ-1:** Should the system prompt be per-run only, or should users be able to save named prompt templates at the project level? Deferred to after v1 usage observation.

**OQ-2:** For the `unclear` claim label: should it count as 0, 0.5, or be excluded from the faithfulness score denominator? Current spec treats it as not-supported (counts in denominator, not in numerator). Revisit after seeing real judge output distributions.

**OQ-3:** Parallelism level for item processing — default of 3 concurrent items chosen conservatively. Should this be user-configurable per run? Deferred.

**OQ-4:** Should eval runs be comparable across different golden sets (e.g., if items are added over time)? Current spec does not constrain this; delta indicators only compare runs with the same golden set ID.

---

## 12. Future Scope (not v1)

- **Correctness scoring:** Judge comparison against `reference_answer`. Schema supports it; scorer and UI deferred.
- **Playground answer eval:** One-click evaluation of a single answer in the index playground, reusing the judge service.
- **Trend visualisation:** Score over time charts on the run list and individual metric pages.
- **Custom judge prompts:** User-defined judge prompt templates at the project level.
- **Claim-level citation linking:** Highlighting the specific chunk sentence that supports each claim, rather than chunk-level attribution.
- **Comparative run view:** Side-by-side metric comparison for two selected runs.
