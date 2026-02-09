# Index Playground Component — Technical Specification

## Overview

The Playground is a retrieval testing tool embedded within the Index Details page of RAG Admin. It allows semi-technical users (PMs, analysts) to run queries against an index, adjust retrieval parameters, and evaluate whether the right chunks are returned — providing a quick "gut check" before running formal evaluations.

**Target persona:** Semi-technical PM/analyst evaluating retrieval quality.
**Key principle:** Simple by default, powerful when needed.

---

## Architecture

### Page Layout Context

The Playground lives as a tab within the redesigned Index Details page. The page structure is:

1. **Persistent Index Header** — always visible at top (name, status, stats, config drawer)
2. **Section Tabs** — "Content" and "Playground"
3. **Main Content Area** — switches based on active tab

When the Playground tab is active, the main content area renders as a **two-panel side-by-side layout**. The query input lives on the right above the results — this keeps the user's primary workflow (type query → see results) in a single vertical flow, while parameters stay accessible on the left as a persistent sidebar.

```
┌─────────────────────────────────────────────────────────────────┐
│  Index Header (persistent)                                       │
├─────────────────────────────────────────────────────────────────┤
│  [Content]  [Playground]                                         │
├──────────────┬──────────────────────────────────────────────────┤
│              │  ┌────────────────────────────────────────────┐   │
│  Retrieval   │  │  Query Input  +  [Search] button           │   │
│  Parameters  │  │  Results summary bar                       │   │
│              │  └────────────────────────────────────────────┘   │
│  ──────────  │                                                   │
│              │  Result Card #1  (rank, score, content, feedback) │
│  Query       │  Result Card #2                                   │
│  History     │  Result Card #3                                   │
│              │  ...                                               │
│  (264px)     │  (flex: 1, remaining width)                       │
└──────────────┴──────────────────────────────────────────────────┘
```

---

## Component Hierarchy

```
IndexDetailsPage
├── IndexHeader (persistent)
│   ├── EditableName
│   ├── EditableDescription
│   ├── StatusBadge
│   ├── StatsRow (documents, chunks, avg tokens, model, dimensions)
│   └── ConfigDrawer (collapsible)
├── SectionTabs
│   ├── ContentTab
│   └── PlaygroundTab
└── PlaygroundPanel (when active)
    ├── ParametersSidebar (left, 264px)
    │   ├── RetrievalParameters
    │   │   ├── SearchTypeToggle
    │   │   ├── TopKSlider
    │   │   └── ThresholdSlider
    │   └── QueryHistory
    └── MainArea (right, flex)
        ├── QueryBar (textarea + search button + results summary)
        ├── ResultsPanel (scrollable list below query bar)
        │   ├── ResultCard[]
        │   │   ├── RankBadge
        │   │   ├── ScoreBar
        │   │   ├── ContentPreview (expandable)
        │   │   ├── SourceMetadata
        │   │   └── FeedbackButtons (thumbs up/down)
        │   └── EmptyState / LoadingState
        └── (no results state)
```

---

## API Integration

### Retrieval Endpoint

The Playground calls the existing retrieval/search API endpoint.

**Request:**
```
POST /api/v1/indexes/{index_id}/query
```

```json
{
  "query": "string — the natural language query",
  "search_type": "semantic | keyword | hybrid",
  "top_k": 5,
  "similarity_threshold": 0.0,
  "project_id": "uuid — current project context"
}
```

**Response:**
```json
{
  "query": "original query text",
  "results": [
    {
      "chunk_id": "uuid",
      "rank": 1,
      "score": 0.94,
      "content": "full chunk text content",
      "metadata": {
        "document_id": "uuid",
        "document_name": "ACPL-IM.pdf",
        "page": 5,
        "chunk_index": 42,
        "token_count": 103,
        "char_count": 456
      }
    }
  ],
  "total_results": 5,
  "search_type": "hybrid",
  "execution_time_ms": 142
}
```

> **Note for backend implementation:** If this endpoint does not exist yet, it should be created. The endpoint should accept the retrieval parameters and return ranked chunks with similarity scores and source metadata. The endpoint should respect the project context for multi-tenancy.

### Feedback Endpoint (Optional / Phase 2)

```
POST /api/v1/indexes/{index_id}/feedback
```

```json
{
  "query": "original query",
  "chunk_id": "uuid",
  "rank": 1,
  "score": 0.94,
  "feedback": "relevant | not_relevant",
  "search_type": "hybrid",
  "top_k": 5,
  "similarity_threshold": 0.0
}
```

This is optional for v1. The thumbs up/down buttons can be session-only (React state) initially and persisted later. Even session-only feedback is valuable because it keeps the user engaged and primes them for the full eval feature.

---

## Component Specifications

### 1. QueryBar

A horizontal bar at the top of the right panel containing the query textarea and search button, with an optional results summary row below.

**Layout:**
- Textarea (flex: 1) + Search button side by side
- When results exist, a summary row appears below showing result count, query text, and active parameter values
- Contained in a single `Card` component

**Behavior:**
- Placeholder text: "What would your users ask? Try a natural language query..."
- Submit on button click or Enter (Shift+Enter for newline)
- Disable button when input is empty or search is in progress
- Clear results and reset feedback state when a new query is submitted
- Auto-focus on tab activation

**Dimensions:**
- Full width of the right panel
- Textarea: 2 rows default, resizable vertically
- Search button: right-aligned, matches textarea height

### 2. RetrievalParameters

Three controls with smart defaults and plain-language tooltips.

#### SearchTypeToggle
- **Options:** Semantic, Keyword, Hybrid
- **Default:** Hybrid
- **UI:** Segmented control (three buttons in a pill shape)
- **Tooltip:** "Semantic finds conceptually similar content. Keyword matches exact words. Hybrid combines both."

#### TopKSlider
- **Range:** 1–20
- **Default:** 5
- **Step:** 1
- **UI:** Range slider with current value displayed
- **Tooltip:** "Number of chunks to retrieve. More results = broader recall but potentially lower precision."
- **Labels:** "1" on left, "20" on right

#### ThresholdSlider
- **Range:** 0.0–1.0
- **Default:** 0.0 (return everything)
- **Step:** 0.1
- **UI:** Range slider with current value displayed to 1 decimal
- **Tooltip:** "Only show results above this relevance score. Higher = stricter matching, fewer results."
- **Labels:** "0.0 (all)" on left, "1.0 (strict)" on right

**Important:** Changing parameters does NOT auto-re-run the query. The user must click "Run Retrieval" again. This is intentional — it lets them adjust multiple parameters before re-running and avoids confusing intermediate states.

### 3. QueryHistory

A session-scoped list of recent queries (max 8).

**Behavior:**
- Appears only after the first query is run
- Clicking a history item populates the query input (does not auto-run)
- Most recent query at top
- De-duplicated (same query text not repeated)
- Cleared on page reload (session-only)
- Each item shows the query text, truncated with ellipsis if too long

### 4. ResultsPanel

The right side of the Playground, showing query results.

#### States:

**Empty State (no query run yet):**
- Centered placeholder with search icon
- Heading: "Run a query to test retrieval"
- Subtext: "Type a question your users might ask and see which chunks come back. Adjust parameters to compare results."

**Loading State:**
- Centered spinner
- Text: "Searching {chunk_count} chunks..."

**Results State:**
- Results header showing: count, original query, and parameter summary
- Scrollable list of ResultCard components

**No Results State (query run but 0 results):**
- Message: "No chunks matched your query with the current parameters."
- Suggestion: "Try lowering the similarity threshold or using a different search type."

### 5. ResultCard

Each result is displayed as a card with the following sections:

#### Header Row
- **Rank badge:** "#1", "#2", etc. in a small rounded square
- **Score bar:** Visual indicator + numeric score (0.00–1.00)
  - Green (≥0.85): strong match
  - Yellow (≥0.70): moderate match
  - Orange (≥0.50): weak match
  - Red (<0.50): poor match
- **Feedback buttons:** Thumbs up / thumbs down (right-aligned)
  - Toggle behavior: clicking again deselects
  - Visual states: default (muted), selected-positive (green), selected-negative (red)

#### Content Section
- First ~200 characters of chunk content displayed
- "Show full chunk" expand/collapse toggle if content exceeds preview length
- Query terms highlighted within content (bold or background highlight)

#### Source Metadata Row
- Document name (with file icon)
- Page number
- Chunk ID/index
- Token count

---

## State Management

All Playground state is local to the component (React useState). No global state management needed.

```typescript
interface PlaygroundState {
  // Input
  query: string;
  searchType: 'semantic' | 'keyword' | 'hybrid';
  topK: number;
  threshold: number;

  // Results
  results: RetrievalResult[];
  isSearching: boolean;
  error: string | null;
  executionTimeMs: number | null;

  // UI
  queryHistory: string[];
  expandedResultId: string | null;
  votes: Record<string, 'up' | 'down' | null>;
}
```

---

## Error Handling

- **Network error:** Show inline error message above results: "Failed to run query. Check your connection and try again." with a "Retry" button.
- **Timeout:** If the query takes >10 seconds, show a warning: "This is taking longer than expected..." but don't cancel.
- **Server error (5xx):** "Something went wrong on the server. Try again or check the index status."
- **Index not ready:** If index status is not "ready", disable the Run button and show: "Index is still processing. Playground will be available once processing is complete."

---

## Responsive Behavior

- **≥1200px:** Full two-panel layout — 264px parameters sidebar + flex-1 main area (query bar + results)
- **900–1199px:** Sidebar narrows to 220px, main area takes remaining space
- **<900px:** Stack vertically — parameters collapse into a horizontal bar or expandable section above the query bar. Query bar and results stack naturally.

---

## Accessibility

- All form controls have associated labels (even if visually hidden)
- Tooltips accessible via keyboard focus (not just hover)
- Score bar has aria-label with the numeric score value
- Feedback buttons have aria-pressed state
- Results list is a proper ordered list semantically
- Loading state has aria-live="polite" announcement
- Color is not the only indicator for score quality (numeric value always shown alongside bar)

---

## Future Enhancements (Out of Scope for v1)

These are noted for architectural awareness but should NOT be implemented in v1:

1. **Persistent feedback storage** — Save thumbs up/down to database for later analysis
2. **Compare mode** — Run the same query with different parameters side by side
3. **Reranking toggle** — Add reranker selection as an advanced parameter
4. **Filter by document** — Scope retrieval to specific documents in the index
5. **Export results** — Download query + results as JSON/CSV for external analysis
6. **Query suggestions** — Auto-suggest queries based on indexed content
7. **Chunk size override** — Re-chunk on the fly with different sizes (computationally expensive)
8. **Execution time display** — Show how long the retrieval took (useful for performance tuning)

---

## Implementation Notes for Claude Code

### Design System: shadcn/ui

The implementation **must** use [shadcn/ui](https://ui.shadcn.com/) components as the design system. Map wireframe elements to shadcn components as follows:

| Wireframe Element | shadcn Component |
|---|---|
| Index header card, parameter panel, query bar, result cards | `Card`, `CardHeader`, `CardContent` |
| Section tabs (Content / Playground) | `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` |
| Search type toggle | `ToggleGroup`, `ToggleGroupItem` (or segmented variant of `Tabs`) |
| Top-K and Threshold sliders | `Slider` + `Label` |
| Query textarea | `Textarea` |
| Search button | `Button` (default variant when active, `secondary` when disabled) |
| Tooltips on parameter labels | `Tooltip`, `TooltipTrigger`, `TooltipContent`, `TooltipProvider` |
| Status badge | `Badge` (variant: `outline` or custom `success`) |
| Config drawer | `Collapsible`, `CollapsibleTrigger`, `CollapsibleContent` |
| Chunk detail panel | `Sheet` (side panel) or a card — either works |
| Document expand/collapse | `Collapsible` |
| Feedback buttons | `Button` (variant: `ghost`, size: `icon`) |
| Chunk table | `Table`, `TableHeader`, `TableRow`, `TableHead`, `TableBody`, `TableCell` |
| Empty/loading states | Use shadcn patterns (centered content with muted text) |

Use shadcn's default theme tokens (`zinc` scale for neutrals, `primary` for actions). The wireframe uses `zinc-900` as the primary action color (buttons, active tab borders) which aligns with shadcn's default neutral-based theming.

### File Structure (suggested)

```
src/
  features/
    indexes/
      components/
        IndexDetailsPage.tsx          # Main page container
        IndexHeader.tsx               # Persistent header with editable name/desc
        ConfigDrawer.tsx              # Collapsible config panel
        ContentPanel.tsx              # Documents + chunks view
        PlaygroundPanel.tsx           # Main playground container
        QueryInput.tsx                # Textarea + run button
        RetrievalParameters.tsx       # The three parameter controls
        QueryHistory.tsx              # Session query history list
        ResultsPanel.tsx              # Results container with states
        ResultCard.tsx                # Individual result display
        ScoreBar.tsx                  # Visual score indicator
        FeedbackButtons.tsx           # Thumbs up/down toggle
      hooks/
        usePlayground.ts              # Playground state + API call logic
        useIndexDetails.ts            # Index data fetching
      types/
        playground.ts                 # TypeScript interfaces
```

### Key Implementation Details

1. **The QueryInput should debounce nothing** — this is an explicit action (click Run), not a type-ahead search. Do not auto-search on input change.

2. **Score color thresholds** should be defined as a shared utility since they may be reused in eval features later:
   ```typescript
   export function getScoreColor(score: number): string {
     if (score >= 0.85) return 'green';
     if (score >= 0.70) return 'yellow';
     if (score >= 0.50) return 'orange';
     return 'red';
   }
   ```

3. **Query highlighting in results** — Use a simple substring match approach. Split the query into words, wrap matches in a `<mark>` tag. Don't over-engineer this with fuzzy matching.

4. **The playground hook** should expose a clean interface:
   ```typescript
   const {
     query, setQuery,
     searchType, setSearchType,
     topK, setTopK,
     threshold, setThreshold,
     results, isSearching, error,
     runSearch,
     queryHistory,
     votes, setVote,
     expandedResultId, setExpandedResultId,
   } = usePlayground(indexId);
   ```

5. **Use shadcn/ui components throughout.** Do not create custom styled components when a shadcn equivalent exists. This ensures consistency with the rest of RAG Admin. If a shadcn component doesn't exist for a specific need (e.g., the ScoreBar), create a small custom component that follows shadcn's design patterns (zinc color scale, rounded-md borders, text-sm sizing).

---

## Wireframe Reference

A visual React prototype accompanies this spec. See `index-details-wireframe.jsx` for the interactive wireframe showing the full page layout including the Playground panel, result cards, parameter controls, and state transitions.
