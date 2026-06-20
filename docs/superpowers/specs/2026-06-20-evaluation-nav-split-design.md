---
title: Evaluation Navigation Split
date: 2026-06-20
status: approved
---

# Evaluation Navigation Split

## Problem

The Evaluation page currently combines Retrieval and Extraction evaluation into a single page with a toggle group. As each domain grows, they deserve their own dedicated page and nav entry for clarity and direct linking.

## Goal

Split the single Evaluation page into two separate pages — Retrieval Evaluation and Extraction Evaluation — and expose them as sub-items under a collapsible "Evaluation" section in the sidebar.

## URL Structure

| Page | Route |
|------|-------|
| Retrieval Evaluation | `/evaluation/retrieval` |
| Extraction Evaluation | `/evaluation/extraction` |

All existing child routes (`/evaluation/runs/:runId`, `/evaluation/golden-sets/:id`, etc.) are unchanged.

The top-level `/evaluation` route is removed. The "Evaluation" sidebar item is a non-linked collapsible header.

## Navigation Config (`navigation.ts`)

Add an optional `children` field to nav items:

```ts
type NavChild = { label: string; href: string }
type NavItem = {
  label: string
  href: string          // empty string '' for non-linked parents
  icon: LucideIcon
  activeColor: string
  children?: NavChild[]
}
```

The Evaluation entry becomes:

```ts
{
  label: 'Evaluation',
  href: '',
  icon: BarChart3,
  activeColor: 'border-l-amber-500',
  children: [
    { label: 'Retrieval', href: '/evaluation/retrieval' },
    { label: 'Extraction', href: '/evaluation/extraction' },
  ],
}
```

## Sidebar (`AppSidebar.tsx`)

Items with a `children` array render as a collapsible section:

- The parent renders as a non-linked `SidebarMenuButton` (no `asChild`/`NavLink`). Clicking it toggles the sub-menu open/closed via local state.
- Children render using `SidebarMenuSub` → `SidebarMenuSubItem` → `SidebarMenuSubButton asChild` with `NavLink`.
- Active state on the parent: true if `location.pathname.startsWith` any child's href.
- Sub-menu starts open if any child is currently active.

## Pages

### `RetrievalEvaluationPage.tsx` (new)

Extracted directly from the retrieval domain of `EvaluationPage.tsx`:

- Tabs: Runs, Experiments, Golden Sets
- Hooks: `useEvalRuns`, `useExperiments`, `useGoldenSets`
- Page heading: "Retrieval Evaluation"

### `ExtractionEvaluationPage.tsx` (reworked)

Currently only has Runs. Rework to add Ground Truth as a second tab:

- Tab bar: Runs | Ground Truth
- Runs tab: `ExtractionEvalRunsTab`
- Ground Truth tab: `ExtractionGroundTruthTab`
- Page heading: "Extraction Evaluation"

### Deleted pages

- `EvaluationPage.tsx` — content split into the two new pages above
- `ExtractionGroundTruthPage.tsx` — functionality absorbed into reworked `ExtractionEvaluationPage`

## Routing (`App.tsx`)

Remove:
```ts
{ path: 'evaluation', element: <EvaluationPage /> }
```

Add:
```ts
{ path: 'evaluation/retrieval', element: <RetrievalEvaluationPage />, handle: { breadcrumb: 'Retrieval Evaluation' } },
{ path: 'evaluation/extraction', element: <ExtractionEvaluationPage />, handle: { breadcrumb: 'Extraction Evaluation' } },
```

All other evaluation child routes remain unchanged.

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/config/navigation.ts` | Add `children` to nav item type; update Evaluation entry |
| `frontend/src/components/layout/AppSidebar.tsx` | Render collapsible sub-menus for items with children |
| `frontend/src/pages/RetrievalEvaluationPage.tsx` | New — retrieval tabs extracted from EvaluationPage |
| `frontend/src/pages/ExtractionEvaluationPage.tsx` | Rework — add Ground Truth tab |
| `frontend/src/pages/EvaluationPage.tsx` | Delete |
| `frontend/src/pages/ExtractionGroundTruthPage.tsx` | Delete |
| `frontend/src/App.tsx` | Update routes |

## Out of Scope

- No changes to backend routes or APIs
- No changes to existing evaluation child pages (EvalRunDetailPage, GoldenSetEditorPage, etc.)
- No changes to other nav items
