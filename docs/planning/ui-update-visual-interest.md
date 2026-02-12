# UI Update: Visual Interest Through Color

## Current State

The UI is built on a **pure grayscale palette** — all CSS variables in `index.css` have zero saturation. The only color comes from destructive (red) states and a few specialized badge variants in the evaluation feature. This makes the app functional but visually flat.

## Completed

### 1. Brand Primary Color — Teal

**File:** `frontend/src/index.css`

Changed `--primary`, `--ring`, and `--sidebar-primary` from grayscale to teal:

| Variable | Light Mode (old) | Light Mode (new) | Dark Mode (new) |
|---|---|---|---|
| `--primary` | `0 0% 9%` | `173 58% 39%` | `173 58% 52%` |
| `--ring` | `0 0% 3.9%` | `173 58% 39%` | `173 58% 52%` |
| `--sidebar-primary` | `240 5.9% 10%` | `173 58% 39%` | `173 58% 52%` |

**Elements affected globally:** primary buttons, default badges, active sidebar items, focus rings, project tags (`bg-primary/10 text-primary`), link-style buttons.

---

## Remaining Suggestions

### 2. Tint Muted/Background Surfaces — Done

**File:** `frontend/src/index.css`

Added a subtle teal tint (hue 175) to `--muted`, `--secondary`, `--accent`, `--muted-foreground`, `--sidebar-background`, and `--sidebar-accent` in both light and dark modes. Surfaces now carry a cool undertone that harmonizes with the teal primary.

| Variable | Light Mode | Dark Mode |
|---|---|---|
| `--secondary` / `--muted` / `--accent` | `175 10% 95.5%` | `175 6% 14.5%` |
| `--muted-foreground` | `175 5% 42%` | `175 4% 63%` |
| `--sidebar-background` | `175 8% 97.5%` | (unchanged) |
| `--sidebar-accent` | `175 12% 93%` | (unchanged) |

### 3. Unify Status Colors Across Components — Done

All three status badge components now use the same color convention via shared badge variants:

| Status | Color | Badge Variant | Used In |
|---|---|---|---|
| Ready / Success / Completed | Green | `success` | Index, Document, Eval |
| Processing / Running | Blue | `blue` | Index, Document, Eval |
| Pending / Draft | Amber | `warning` | Eval |
| Failed / Error | Red | `destructive` | Index, Document, Eval |
| Created / New | Gray | `outline` | Index |

**Files changed:**
- `IndexStatusBadge.tsx` — `ready` → `success`, `processing` → `blue` (was `default`/`secondary`)
- `DocumentStatusBadge.tsx` — Rewritten to use `<Badge>` component with shared variants (was custom inline styles with SVG icons)
- `IndexDetailPage.tsx:470` — Inline status text uses status-aware colors instead of hardcoded `text-emerald-600`
- `IndexDetailPage.tsx:361` — Error box gets dark mode support (`dark:bg-red-950/30 dark:text-red-400`)
- `EvalStatusBadge.tsx` — Already correct (no changes needed)

### 4. Migrate IndexDetailPage Off Hardcoded Zinc Classes — Done

**File:** `frontend/src/pages/IndexDetailPage.tsx`

Removed all ~50 hardcoded `zinc-*` classes. Zero `zinc` references remain. Mapping applied:

| Old (zinc) | New (design system) |
|---|---|
| `bg-white` | `bg-background` |
| `border-zinc-100/200/300` | `border` (uses CSS variable) |
| `bg-zinc-50` | `bg-muted/50` |
| `bg-zinc-100` | `bg-muted` |
| `text-zinc-300` | `text-muted-foreground/40` |
| `text-zinc-400/500` | `text-muted-foreground` |
| `text-zinc-600/700/800/900` | `text-foreground` |
| `hover:bg-zinc-50` | `hover:bg-muted/50` |
| `hover:bg-zinc-100` | `hover:bg-muted` |
| `border-zinc-900` (active tab) | `border-primary` |
| `focus:ring-zinc-900` | `focus:ring-ring` |
| `divide-zinc-100` | `divide-border` |

Active tab underline now uses `border-primary` (teal) instead of `border-zinc-900`.

### 5. Add Color Accents to Dashboard — Done

**File:** `frontend/src/pages/DashboardPage.tsx`

Complete dashboard redesign replacing the placeholder welcome card with live project data:

- **4 stat cards** with distinct color accents:
  - Documents (blue), Indexes (teal), Eval Runs (amber), Golden Sets (violet)
  - Each card has: colored left border, tinted icon background, large count, status breakdown bar
- **Status breakdown mini-bars** per card showing green (ready/completed), blue (processing/running), amber (pending), red (failed)
- **Recent Activity feed** combining latest indexes and eval runs, sorted by date, with colored status icons and click-through navigation
- All cards are clickable, navigating to their respective pages
- Loading skeletons while data fetches
- Uses existing hooks: `useDocuments`, `useIndexes`, `useEvalRuns`, `useGoldenSets`

### 6. Colored Header Accent Line — Done

**File:** `frontend/src/index.css`

Added a fixed 3px teal accent line at the very top of the viewport via `body::before`. Uses `position: fixed` with `z-index: 100` so it spans the full width above the sidebar and content.

### 7. Color-Code Sidebar Navigation Sections — Done

**Files:** `frontend/src/config/navigation.ts`, `frontend/src/components/layout/AppSidebar.tsx`

Added an `activeColor` field to each nav item and a 3px left-border indicator on the active sidebar button:

| Section | Color |
|---|---|
| Dashboard | Teal (primary) |
| Projects | Violet |
| Documents | Blue |
| Index | Teal |
| Evaluation | Amber |
| Settings | Gray |

Inactive items get a transparent left border to prevent layout shift.

### 8. Improve Interactive Affordances with Color — Done

**Files changed:**
- `components/ui/table.tsx` — default `TableRow` hover changed from `bg-muted/50` to `bg-primary/5`
- `components/documents/DocumentsTable.tsx` — row hover changed from `bg-muted/30` to `bg-primary/5`
- `pages/IndexDetailPage.tsx` — document rows and chunk rows use `bg-primary/5` hover, selected chunk uses `bg-primary/10`
- `pages/DashboardPage.tsx` — activity rows use `bg-primary/5` hover
- `components/indexes/IndexCard.tsx` — index name gets `hover:text-primary` and is clickable
- Active tabs already use `border-primary` (done in step 4)

---

## Priority Order

1. ~~Brand primary color (teal)~~ — Done
2. ~~Tint muted/background surfaces~~ — Done
3. ~~Unify status colors~~ — Done
4. ~~Migrate IndexDetailPage off hardcoded zinc~~ — Done
5. ~~Dashboard color accents~~ — Done
6. ~~Header accent line~~ — Done
7. ~~Sidebar section color-coding~~ — Done
8. ~~Interactive affordance improvements~~ — Done
