# Evaluation & Experiments — Verification Spec

This document covers both **manual browser-based verification** and **automated test specifications** for the full Evaluation feature: experiments, eval runs, golden sets, clone flow, and variable diff.

---

## Part 1: Manual Browser-Based E2E Verification

### Prerequisites

1. Apply the migration:
   ```bash
   docker compose -f docker-compose.local.yml exec backend alembic upgrade head
   ```
2. Rebuild and restart backend:
   ```bash
   docker compose -f docker-compose.local.yml up -d --build backend
   ```
3. Start frontend dev server:
   ```bash
   cd frontend && npm run dev
   ```
4. Ensure you have at least one **ready index**, one **golden set with queries**, and optionally LLM provider keys configured.

---

### 1. Create an Experiment

1. Navigate to `/evaluation`.
2. Click the **Experiments** tab (between Runs and Golden Sets).
3. Verify the empty state shows the flask icon and "No experiments yet" message.
4. Click **New Experiment**.
5. In the dialog:
   - Enter name: `Does hybrid search improve recall?`
   - Enter description: `Testing hybrid vs semantic search with same index`
   - Click **Create**.
6. **Verify**: You are navigated to `/evaluation/experiments/<id>`.
7. **Verify**: Header shows the name, "active" badge (blue), and description text.
8. **Verify**: Leaderboard shows empty state: "No runs yet. Click New Variant to create the first run."
9. **Verify**: Notes section is an empty textarea.
10. **Verify**: "Conclude Experiment" button is visible. "Compare" button is NOT visible.

### 2. Create First Run (Baseline) via New Variant

1. On the experiment detail page, click **New Variant**.
2. **Verify**: URL is `/evaluation/runs/new?experiment=<experimentId>` (no `clone` param since no baseline yet).
3. **Verify**: Back arrow and Cancel button navigate to the experiment detail page, not `/evaluation`.
4. **Verify**: "Variant Label" field is visible below Run Name (only shows when `experiment` param is present).
5. **Verify**: No blue clone banner is shown.
6. Fill in the form:
   - Mode: Retrieval Only
   - Golden Set: pick one
   - Index: pick one
   - Search Mode: Semantic
   - Top K: 5
   - Name: `Baseline — semantic k=5`
   - Variant Label: `semantic, topK=5`
7. Click **Run Evaluation**.
8. **Verify**: Navigated to the run detail page `/evaluation/runs/<runId>`.
9. Wait for the run to complete.

### 3. Verify Run Appears in Experiment

1. Navigate back to `/evaluation/experiments/<id>`.
2. **Verify**: Leaderboard now shows 1 row with the run you created.
3. **Verify**: Run shows metrics once completed (P@k, R@k, F1 as percentages).
4. **Verify**: Variant column shows `semantic, topK=5`.
5. **Verify**: "What Varies" card is NOT shown (needs 2+ runs).
6. **Verify**: "Compare" button is NOT shown (needs 2+ completed runs).

### 4. Set Baseline

1. In the leaderboard, click the `...` menu on the completed run's row.
2. Click **Set as Baseline**.
3. **Verify**: The row now shows a filled amber star icon on the left.
4. **Verify**: The row has a light primary background tint.

### 5. Create Second Run (Variant) via Clone

1. Click **New Variant** again.
2. **Verify**: URL is `/evaluation/runs/new?experiment=<id>&clone=<baselineRunId>`.
3. **Verify**: Blue banner: "Creating variant based on **Baseline — semantic k=5**. Change the variable you want to test."
4. **Verify**: All fields are pre-filled from the baseline run:
   - Same golden set selected
   - Same index selected
   - Mode: Retrieval Only
   - Search Mode: Semantic
   - Top K: 5
5. Change the variable:
   - Search Mode: **Hybrid**
   - Top K: **10**
   - Name: `Variant — hybrid k=10`
   - Variant Label: `hybrid, topK=10`
6. Click **Run Evaluation**.
7. Wait for completion.

### 6. Verify Leaderboard with 2 Runs

1. Navigate back to the experiment detail.
2. **Verify**: Leaderboard shows 2 rows.
3. **Verify**: Baseline row (star icon) has light highlighted background.
4. **Verify**: Runs are sorted: baseline pinned to top, then by F1 descending.
5. **Verify**: Non-baseline row shows F1 delta next to the F1 value:
   - Green `+X.X` if F1 improved
   - Red `-X.X` if F1 regressed
   - Nothing if delta is near zero
6. **Verify**: Clicking a row navigates to `/evaluation/runs/<runId>`.

### 7. Verify Variable Diff Panel

1. Scroll to the **"What Varies"** card.
2. **Verify**: Card is now visible (2+ runs).
3. **Verify** varying section shows fields that differ across runs:
   - `searchType`: badges showing `semantic` and `hybrid`
   - `topK`: badges showing `5` and `10`
4. **Verify** "Held Constant" section shows fields that are the same:
   - `index`: same index name
   - `mode`: `retrieval_only`
   - `similarityThreshold`: `0`
   - `generationModel`: `—`
   - `judgeModel`: `—`

### 8. Verify Compare Button

1. **Verify**: "Compare" button is now visible (2 completed runs).
2. Click **Compare**.
3. **Verify**: Navigated to `/evaluation/compare?runs=<id1>,<id2>`.
4. **Verify**: Comparison page loads with both runs.

### 9. Verify Notes

1. Navigate back to the experiment detail.
2. In the Notes textarea, type: `Hybrid search shows +3% F1 improvement.`
3. Click outside the textarea (blur event).
4. Hard-refresh the page (Ctrl+Shift+R).
5. **Verify**: Notes text is persisted and displays correctly.

### 10. Edit Experiment Name/Description

1. Click the pencil icon next to the experiment name.
2. **Verify**: Name and description become editable Input fields.
3. Change the name to `Hybrid vs Semantic — recall test`.
4. Click **Save**.
5. **Verify**: Header updates with the new name. Edit mode exits.
6. Click pencil, then click **Cancel**.
7. **Verify**: No changes are saved; original name remains.

### 11. Conclude Experiment

1. Click **Conclude Experiment**.
2. **Verify**: Status badge changes from "active" (blue) to "concluded" (gray/secondary).
3. **Verify**: "Conclude Experiment" button disappears.
4. **Verify**: "New Variant" button still works.

### 12. Verify Runs Tab — Experiment Column

1. Navigate to `/evaluation` → **Runs** tab.
2. **Verify**: "Experiment" column appears between Name and Mode.
3. **Verify**: Runs linked to the experiment show the experiment name as a blue clickable link.
4. **Verify**: Runs created without an experiment show "—" in gray.
5. Click an experiment name link.
6. **Verify**: Navigated to `/evaluation/experiments/<id>`.

### 13. Verify Experiments Tab List

1. Navigate to `/evaluation` → **Experiments** tab.
2. **Verify**: Table columns: Name | Status | Runs | Baseline F1 | Created | (delete)
3. **Verify**: Row shows:
   - Name + description snippet
   - Status badge: concluded
   - Run count: 2
   - Baseline F1: percentage from baseline run metrics
   - Created date
4. **Verify**: Row is clickable → navigates to detail page.
5. **Verify**: Trash icon is present per row.

### 14. Edge Case: Delete Experiment

1. On the Experiments tab, click the trash icon.
2. **Verify**: Experiment is removed from the list.
3. Navigate to **Runs** tab.
4. **Verify**: Runs that were in the experiment **still exist** (not deleted).
5. **Verify**: Their Experiment column now shows "—" (unlinked).

### 15. Edge Case: Experiment with 0 Runs

1. Create a new experiment.
2. Navigate to its detail page.
3. **Verify**: Leaderboard shows empty state message.
4. **Verify**: No "What Varies" card.
5. **Verify**: No "Compare" button.
6. **Verify**: "New Variant" → URL has `experiment=<id>` but no `clone` param.

### 16. Edge Case: Standalone Run (no experiment)

1. Navigate to **Runs** tab → **New Run**.
2. **Verify**: No clone banner, no variant label field.
3. **Verify**: Back arrow and Cancel → `/evaluation`.
4. Create and run the evaluation.
5. **Verify**: Run appears with Experiment column = "—".

### 17. Edge Case: Answer Mode Clone

1. Create an experiment.
2. Create a baseline run with mode = **Retrieval + Answer** (requires LLM keys).
3. Set as baseline.
4. Click **New Variant**.
5. **Verify**: Mode pre-selects "Retrieval + Answer".
6. **Verify**: Generation model and judge model are pre-filled.
7. **Verify**: System prompt is pre-filled.
8. Change only the generation model, submit.
9. **Verify**: Variable diff shows `generationModel` as varying.

---

## Part 2: Automated Test Specifications

### Test Infrastructure

| Layer | Framework | Location | Runner |
|---|---|---|---|
| Backend unit/integration | pytest + pytest-asyncio | `backend/tests/` | `pytest` |
| Backend DB | In-memory SQLite via `aiosqlite` | `backend/tests/conftest.py` | — |
| Backend API | `httpx.AsyncClient` + `ASGITransport` | `backend/tests/routers/` | `pytest` |
| Frontend unit | Vitest + React Testing Library | `frontend/src/**/*.test.ts(x)` | `npx vitest` |
| Frontend E2E | Playwright (suggested) | `frontend/e2e/` | `npx playwright test` |

> **Note**: Frontend testing infrastructure (Vitest, RTL, Playwright) is not yet set up. These specs define what to implement once the framework is installed.

---

### 2A. Backend — Repository Tests

**File**: `backend/tests/repositories/test_experiment_repository.py`

Fixtures needed:
- `test_db` (from conftest)
- `experiment_repo(test_db)` → `ExperimentRepository`
- `eval_run_repo(test_db)` → `EvalRunRepository`
- `test_user` → create a user in DB, return User object
- `test_project` → create a project, return Project object
- `test_golden_set` → create a golden set for the project
- `test_index` → create an index for the project

#### Tests

| Test | What to assert |
|---|---|
| `test_create_experiment` | Returns Experiment with correct name, description, project_id, status=active, created_by, timestamps |
| `test_create_experiment_minimal` | description=None works |
| `test_get_by_id_found` | Returns experiment with baseline_run and runs eagerly loaded |
| `test_get_by_id_not_found` | Returns None for non-existent ID |
| `test_get_by_id_wrong_project` | Returns None when project_id doesn't match |
| `test_list_by_project` | Returns experiments ordered by created_at desc; only for the given project |
| `test_list_by_project_empty` | Returns empty list when no experiments exist |
| `test_update_name` | Updates name, returns updated experiment |
| `test_update_status` | Updates status from active to concluded |
| `test_update_baseline_run_id` | Sets baseline_run_id to a valid run ID |
| `test_update_notes` | Updates notes field |
| `test_update_not_found` | Returns None for non-existent experiment |
| `test_delete_experiment` | Removes experiment, returns True |
| `test_delete_unlinks_runs` | After delete, eval_runs that had experiment_id set now have experiment_id=None |
| `test_delete_not_found` | Returns False for non-existent experiment |
| `test_get_run_count` | Returns correct count of runs linked to experiment |
| `test_get_run_count_zero` | Returns 0 for experiment with no runs |

**File**: `backend/tests/repositories/test_eval_run_repository.py` (additions)

| Test | What to assert |
|---|---|
| `test_create_with_experiment_id` | Run is created with experiment_id and variant_label set |
| `test_create_without_experiment_id` | experiment_id and variant_label default to None |
| `test_get_by_id_loads_experiment` | Returned run has experiment relationship loaded (not lazy) |
| `test_list_by_project_loads_experiment` | All returned runs have experiment relationship loaded |

---

### 2B. Backend — Service Tests

**File**: `backend/tests/services/test_experiment_service.py`

Fixtures:
- `experiment_repo` (mock or real with test_db)
- `experiment_service(experiment_repo)` → `ExperimentService`

| Test | What to assert |
|---|---|
| `test_create_returns_response` | Returns ExperimentResponse with correct fields, run_count=0 |
| `test_list_by_project` | Returns list of ExperimentResponse with run_count populated |
| `test_get_detail_found` | Returns ExperimentDetailResponse with runs list and variableDiff |
| `test_get_detail_not_found` | Raises NotFoundError |
| `test_update_name_and_status` | Returns updated ExperimentResponse |
| `test_update_not_found` | Raises NotFoundError |
| `test_delete_success` | Does not raise |
| `test_delete_not_found` | Raises NotFoundError |
| `test_compute_variable_diff_no_runs` | Returns empty varying and constant |
| `test_compute_variable_diff_one_run` | Returns empty varying and constant (needs 2+) |
| `test_compute_variable_diff_same_config` | All fields in constant, nothing in varying |
| `test_compute_variable_diff_different_index` | `index` appears in varying, others in constant |
| `test_compute_variable_diff_different_search_type` | `searchType` in varying |
| `test_compute_variable_diff_different_topk` | `topK` in varying |
| `test_compute_variable_diff_different_mode` | `mode` in varying |
| `test_compute_variable_diff_different_models` | `generationModel` and/or `judgeModel` in varying |
| `test_compute_variable_diff_multiple_fields_vary` | Multiple fields in varying, rest in constant |

**File**: `backend/tests/services/test_eval_service.py` (additions)

| Test | What to assert |
|---|---|
| `test_create_run_with_experiment_id` | Run created with experiment_id and variant_label passed through |
| `test_create_run_without_experiment_id` | experiment_id and variant_label are None in response |
| `test_get_run_config` | Returns dict with goldenSetId, indexId, config, mode, generationModel, judgeModel, systemPrompt, experimentId, variantLabel |
| `test_get_run_config_not_found` | Raises NotFoundError |
| `test_to_response_includes_experiment_name` | When run has experiment loaded, experimentName is populated |
| `test_to_response_no_experiment` | When run.experiment is None, experimentName is None |

---

### 2C. Backend — Router / API Tests

**File**: `backend/tests/routers/test_experiments.py`

Helper: `create_user_and_login(client)` → returns access token (reuse from test_projects.py pattern).

Setup helper:
```python
async def create_project(client, token) -> str:
    """Create a project and return its ID."""
    resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Project"}
    )
    return resp.json()["id"]
```

| Test | Method | URL | Status | Assertions |
|---|---|---|---|---|
| `test_create_experiment` | POST | `/projects/{pid}/experiments` | 201 | Response has id, name, description, status=active, runCount=0 |
| `test_create_experiment_minimal` | POST | `/projects/{pid}/experiments` | 201 | description is null, name is set |
| `test_create_experiment_missing_name` | POST | `/projects/{pid}/experiments` | 422 | Validation error |
| `test_create_experiment_unauthenticated` | POST | `/projects/{pid}/experiments` | 401 | Not authenticated |
| `test_create_experiment_wrong_project` | POST | `/projects/{fake}/experiments` | 404 | Project not found |
| `test_list_experiments_empty` | GET | `/projects/{pid}/experiments` | 200 | Empty list |
| `test_list_experiments` | GET | `/projects/{pid}/experiments` | 200 | Contains created experiments, ordered by created_at desc |
| `test_list_experiments_scoped_to_project` | GET | `/projects/{pid}/experiments` | 200 | Only returns experiments for the given project |
| `test_get_experiment_detail` | GET | `/projects/{pid}/experiments/{eid}` | 200 | Has runs list, variableDiff object, baselineRun |
| `test_get_experiment_not_found` | GET | `/projects/{pid}/experiments/{fake}` | 404 | |
| `test_update_experiment_name` | PATCH | `/projects/{pid}/experiments/{eid}` | 200 | name is updated |
| `test_update_experiment_status` | PATCH | `/projects/{pid}/experiments/{eid}` | 200 | status changes to concluded |
| `test_update_experiment_notes` | PATCH | `/projects/{pid}/experiments/{eid}` | 200 | notes field is set |
| `test_update_experiment_baseline` | PATCH | `/projects/{pid}/experiments/{eid}` | 200 | baselineRunId is set |
| `test_update_experiment_not_found` | PATCH | `/projects/{pid}/experiments/{fake}` | 404 | |
| `test_delete_experiment` | DELETE | `/projects/{pid}/experiments/{eid}` | 204 | Experiment removed |
| `test_delete_experiment_preserves_runs` | DELETE | `/projects/{pid}/experiments/{eid}` | 204 | Linked runs still exist, experimentId is null |
| `test_delete_experiment_not_found` | DELETE | `/projects/{pid}/experiments/{fake}` | 404 | |

**File**: `backend/tests/routers/test_eval_runs.py` (additions)

| Test | Method | URL | Assertions |
|---|---|---|---|
| `test_create_run_with_experiment_id` | POST | `/projects/{pid}/eval-runs` | Response includes experimentId, variantLabel |
| `test_create_run_experiment_id_in_list` | GET | `/projects/{pid}/eval-runs` | Runs include experimentId, experimentName |
| `test_get_run_config` | GET | `/projects/{pid}/eval-runs/{rid}/config` | Returns dict with all config fields |
| `test_get_run_config_not_found` | GET | `/projects/{pid}/eval-runs/{fake}/config` | 404 |

---

### 2D. Frontend — Unit Tests (Vitest + React Testing Library)

> Requires setup: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `msw` (Mock Service Worker) for API mocking.

#### Hook Tests

**File**: `frontend/src/hooks/useExperiments.test.ts`

Use `renderHook` from `@testing-library/react` and MSW to mock API responses.

| Test | Setup | Assertion |
|---|---|---|
| `useExperiments — fetches on mount` | MSW returns 2 experiments | experiments has length 2 |
| `useExperiments — empty project` | projectId = null | experiments is empty, no API call |
| `useExperiments — createExperiment` | MSW returns created experiment | experiments list includes new item |
| `useExperiments — deleteExperiment` | MSW returns 204 | experiment removed from list |
| `useExperiments — handles error` | MSW returns 500 | error is set, experiments is empty |
| `useExperimentDetail — fetches detail` | MSW returns experiment with runs | experiment has runs array and variableDiff |
| `useExperimentDetail — polls when active runs` | MSW returns experiment with running run | Verify setInterval is called |
| `useExperimentDetail — stops polling when all complete` | Runs transition to completed | Verify clearInterval is called |
| `useExperimentDetail — updateExperiment` | MSW returns updated experiment | experiment reflects new values |

#### Component Tests

**File**: `frontend/src/components/evaluation/ExperimentsTab.test.tsx`

| Test | Props | Assertion |
|---|---|---|
| `renders loading state` | isLoading=true | Loader spinner visible |
| `renders empty state` | experiments=[] | "No experiments yet" text visible |
| `renders experiments table` | 2 experiments | Table has 2 data rows with correct names |
| `clicking row navigates` | 1 experiment | `navigate` called with `/evaluation/experiments/<id>` |
| `clicking New Experiment opens dialog` | — | Dialog becomes visible |
| `clicking delete calls onDelete` | 1 experiment | onDelete called with experiment id |
| `displays status badge` | experiment with status=concluded | Badge shows "concluded" |
| `displays baseline F1` | experiment with baselineRun | F1 percentage is rendered |

**File**: `frontend/src/components/evaluation/CreateExperimentDialog.test.tsx`

| Test | Assertion |
|---|---|
| `renders when open` | Dialog content visible with name input, description textarea |
| `submit disabled when name empty` | Create button is disabled |
| `submit enabled with name` | Create button is enabled |
| `calls onCreate and closes` | onCreate called with {name, description}, dialog closes |
| `cancel closes dialog` | onOpenChange(false) called |

**File**: `frontend/src/components/evaluation/EvalRunsTab.test.tsx` (additions)

| Test | Assertion |
|---|---|
| `renders experiment column` | Table header includes "Experiment" |
| `shows experiment name as link` | Run with experimentName renders clickable link |
| `shows dash for ungrouped run` | Run without experimentId renders "—" |
| `clicking experiment name navigates` | navigate called with `/evaluation/experiments/<id>` |

#### Page Tests

**File**: `frontend/src/pages/ExperimentDetailPage.test.tsx`

| Test | Setup (mocked hook data) | Assertion |
|---|---|---|
| `renders loading state` | isLoading=true | Spinner visible |
| `renders experiment header` | experiment with name, status=active | Name text, blue badge visible |
| `renders empty leaderboard` | experiment with 0 runs | Empty state message visible |
| `renders leaderboard with runs` | experiment with 2 completed runs | 2 table rows, metrics displayed |
| `baseline run has star` | run.id === baselineRunId | Star icon visible in first column |
| `non-baseline shows F1 delta` | two runs, different F1 | Delta text (+X.X or -X.X) visible |
| `variable diff panel hidden with <2 runs` | 1 run | "What Varies" card not in DOM |
| `variable diff panel shown with 2+ runs` | 2 runs, variableDiff has varying fields | Card visible, badges rendered |
| `held constant section` | variableDiff.constant has entries | Constant fields rendered |
| `clicking New Variant navigates` | experiment with baseline | navigate called with clone + experiment params |
| `clicking New Variant without baseline` | experiment without baseline | navigate called with experiment param only |
| `set as baseline` | click `...` → Set as Baseline | updateExperiment called with baselineRunId |
| `conclude experiment` | click Conclude | updateExperiment called with status=concluded |
| `conclude button hidden when concluded` | status=concluded | Button not in DOM |
| `notes auto-save on blur` | type text, blur | updateExperiment called with notes |
| `edit name flow` | click pencil, change name, save | updateExperiment called with new name |

**File**: `frontend/src/pages/NewEvalRunPage.test.tsx` (additions for clone flow)

| Test | URL params | Assertion |
|---|---|---|
| `no clone — default state` | none | No banner, no variant label field, title = "New Evaluation Run" |
| `clone param — fetches config` | `?clone=<id>` | getEvalRunConfig called, fields pre-filled |
| `clone param — shows banner` | `?clone=<id>` | Blue banner with source run name visible |
| `experiment param — shows variant label` | `?experiment=<id>` | Variant Label input visible |
| `experiment param — submit includes experimentId` | `?experiment=<id>` | createRun called with experimentId in payload |
| `clone + experiment — full prefill` | `?clone=<id>&experiment=<eid>` | All fields pre-filled, experimentId and variantLabel sent |
| `back button goes to experiment` | `?experiment=<id>` | navigate to `/evaluation/experiments/<id>` |
| `back button goes to evaluation` | none | navigate to `/evaluation` |

---

### 2E. Frontend — E2E Tests (Playwright)

> Requires setup: `@playwright/test`. Tests run against a real dev server with seeded DB.

**File**: `frontend/e2e/experiments.spec.ts`

#### Test Data Setup

Each test suite should seed the database via API calls in `beforeAll`:
1. Sign up / sign in → get auth token
2. Create a project
3. Upload a document + create an index (or use pre-existing seeded data)
4. Create a golden set with at least 2 queries

#### Tests

| Test | Steps | Assertions |
|---|---|---|
| `create experiment flow` | Navigate to /evaluation → Experiments tab → New Experiment → fill form → Create | Redirected to detail page, name displayed |
| `create variant and set baseline` | From experiment detail → New Variant → fill form → Run → wait for complete → set as baseline | Star icon appears on baseline row |
| `clone variant flow` | Set baseline → New Variant → verify prefill → change topK → Run | 2 runs in leaderboard, variable diff shows topK varying |
| `compare from experiment` | 2 completed runs → click Compare | Comparison page loads with both runs |
| `conclude experiment` | Click Conclude → verify badge | Status badge = concluded, button disappears |
| `notes persistence` | Type notes → blur → reload page | Notes text preserved |
| `delete experiment preserves runs` | Delete experiment → go to Runs tab | Runs still exist, experiment column = — |
| `experiment column in runs tab` | Create experiment + run → go to Runs tab | Experiment name shown as link, clicking navigates |
| `experiments list page` | Create 2 experiments → Experiments tab | Both shown in table with correct data |

---

### 2F. Test Data Builders / Fixtures Summary

#### Backend (Python)

```python
# Suggested shared fixture additions for backend/tests/conftest.py

@pytest.fixture
async def test_project(test_db, test_user):
    """Create a test project."""
    repo = ProjectRepository(test_db)
    return await repo.create(name="Test Project", user_id=test_user.id)

@pytest.fixture
async def test_index(test_db, test_project):
    """Create a test index."""
    repo = IndexRepository(test_db)
    return await repo.create(
        project_id=test_project.id,
        name="Test Index",
        # ... minimal required fields
    )

@pytest.fixture
async def test_golden_set(test_db, test_project, test_user):
    """Create a test golden set with queries."""
    repo = GoldenSetRepository(test_db)
    gs = await repo.create(
        project_id=test_project.id,
        name="Test Golden Set",
        user_id=test_user.id,
    )
    # Add 2 queries
    await repo.add_query(gs.id, "What is RAG?")
    await repo.add_query(gs.id, "How does retrieval work?")
    return gs

@pytest.fixture
async def test_experiment(test_db, test_project, test_user):
    """Create a test experiment."""
    repo = ExperimentRepository(test_db)
    return await repo.create(
        project_id=test_project.id,
        name="Test Experiment",
        user_id=test_user.id,
        description="Testing hypothesis",
    )

@pytest.fixture
async def test_eval_run(test_db, test_project, test_golden_set, test_index, test_user):
    """Create a test eval run."""
    repo = EvalRunRepository(test_db)
    return await repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Test Run",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
    )
```

#### Frontend (TypeScript)

```typescript
// Suggested test data builders for frontend tests

export function buildExperiment(overrides?: Partial<Experiment>): Experiment {
  return {
    id: 'exp-1',
    name: 'Test Experiment',
    description: 'A test experiment',
    status: 'active',
    notes: null,
    baselineRunId: null,
    baselineRun: null,
    runCount: 0,
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function buildExperimentDetail(
  overrides?: Partial<ExperimentDetail>
): ExperimentDetail {
  return {
    ...buildExperiment(),
    runs: [],
    variableDiff: { varying: {}, constant: {} },
    ...overrides,
  }
}

export function buildEvalRun(overrides?: Partial<EvalRun>): EvalRun {
  return {
    id: 'run-1',
    name: 'Test Run',
    goldenSetId: 'gs-1',
    goldenSetName: 'Test GS',
    indexId: 'idx-1',
    indexName: 'Test Index',
    config: { searchType: 'semantic', topK: 5, similarityThreshold: 0 },
    status: 'completed',
    metrics: {
      avgPrecision: 0.8,
      avgRecall: 0.7,
      avgF1: 0.75,
      queriesBelowThreshold: 1,
      avgFaithfulness: null,
      avgRelevance: null,
    },
    errorMessage: null,
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    mode: 'retrieval_only',
    generationModel: null,
    judgeModel: null,
    itemsCompleted: 5,
    failedItemCount: 0,
    experimentId: undefined,
    experimentName: undefined,
    variantLabel: undefined,
    ...overrides,
  }
}
```

---

### 2G. Coverage Targets

| Layer | Target | Notes |
|---|---|---|
| Backend repositories | 90%+ | All CRUD paths, edge cases (not found, wrong project) |
| Backend services | 85%+ | Business logic, variable diff computation, error handling |
| Backend routers | 80%+ | All endpoints, auth, validation, error responses |
| Frontend hooks | 80%+ | Fetch, create, delete, polling lifecycle |
| Frontend components | 75%+ | Rendering, interactions, navigation |
| Frontend pages | 70%+ | Integration of hooks + components, clone flow |
| E2E | Critical paths | Create experiment → add runs → compare → conclude |
