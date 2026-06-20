# Evaluation Navigation Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single Evaluation page into Retrieval and Extraction sub-pages and expose them as collapsible sub-items under "Evaluation" in the sidebar.

**Architecture:** Extend the navigation config type to support optional `children`, update AppSidebar to render `SidebarMenuSub` for items with children (using local `useState` for open/closed), create `RetrievalEvaluationPage` by extracting retrieval content from `EvaluationPage`, rework `ExtractionEvaluationPage` to include a Ground Truth tab via `ExtractionEvalRunsTab` + `ExtractionGroundTruthTab`, then update routes and delete the now-redundant pages.

**Tech Stack:** React 18, TypeScript, React Router v6, shadcn/ui (`SidebarMenuSub`, `SidebarMenuSubItem`, `SidebarMenuSubButton`), Tailwind CSS, Vitest + Testing Library

## Global Constraints

- shadcn/ui components only for UI; no new npm dependencies
- All routes remain under the existing `AppLayout` / `PrivateRoute` setup
- Data flow: page → hook → api (no business logic in pages)
- `href: ''` on a nav item signals non-linkable (collapsible header only)
- Spec: `docs/superpowers/specs/2026-06-20-evaluation-nav-split-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/config/navigation.ts` | Modify | Add `NavChild` type + `children?` field; update Evaluation entry |
| `frontend/src/components/layout/AppSidebar.tsx` | Modify | Render collapsible sub-menus for items with children |
| `frontend/src/pages/RetrievalEvaluationPage.tsx` | Create | Retrieval tabs (Runs, Experiments, Golden Sets) |
| `frontend/src/pages/ExtractionEvaluationPage.tsx` | Rework | Add Ground Truth tab alongside Runs |
| `frontend/src/pages/RetrievalEvaluationPage.test.tsx` | Create | Smoke test |
| `frontend/src/pages/ExtractionEvaluationPage.test.tsx` | Create | Tab presence test |
| `frontend/src/App.tsx` | Modify | Swap routes |
| `frontend/src/pages/EvaluationPage.tsx` | Delete | Replaced by the two new pages |
| `frontend/src/pages/ExtractionGroundTruthPage.tsx` | Delete | Functionality absorbed into ExtractionEvaluationPage |

---

### Task 1: Extend navigation config with children support

**Files:**
- Modify: `frontend/src/config/navigation.ts`

**Interfaces:**
- Produces: `NavChild` type and `children?: readonly NavChild[]` field consumed by AppSidebar in Task 2

- [ ] **Step 1: Replace the contents of `frontend/src/config/navigation.ts`**

```ts
import {
  LayoutDashboard,
  FolderKanban,
  FileText,
  Database,
  BarChart3,
  Settings,
  FileSearch,
  Bot,
  HardDrive,
  ArrowUpFromLine,
  Tags,
  type LucideIcon,
} from 'lucide-react'

export type NavChild = { label: string; href: string }

export type NavItem = {
  label: string
  href: string
  icon: LucideIcon
  activeColor: string
  children?: readonly NavChild[]
}

export const navigationItems: readonly NavItem[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard, activeColor: 'border-l-primary' },
  { label: 'Projects', href: '/projects', icon: FolderKanban, activeColor: 'border-l-violet-500' },
  { label: 'Documents', href: '/documents', icon: FileText, activeColor: 'border-l-blue-500' },
  { label: 'Index', href: '/index', icon: Database, activeColor: 'border-l-teal-500' },
  { label: 'Extraction', href: '/extraction', icon: FileSearch, activeColor: 'border-l-orange-500' },
  { label: 'Classify', href: '/classify', icon: Tags, activeColor: 'border-l-pink-500' },
  { label: 'Data Stores', href: '/data-stores', icon: HardDrive, activeColor: 'border-l-cyan-500' },
  { label: 'Export', href: '/export', icon: ArrowUpFromLine, activeColor: 'border-l-emerald-500' },
  {
    label: 'Evaluation',
    href: '',
    icon: BarChart3,
    activeColor: 'border-l-amber-500',
    children: [
      { label: 'Retrieval', href: '/evaluation/retrieval' },
      { label: 'Extraction', href: '/evaluation/extraction' },
    ],
  },
  { label: 'Agents', href: '/agent', icon: Bot, activeColor: 'border-l-purple-500' },
  { label: 'Settings', href: '/settings', icon: Settings, activeColor: 'border-l-gray-400' },
]
```

- [ ] **Step 2: Run TypeScript check to confirm no type errors**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors (or only pre-existing unrelated errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/config/navigation.ts
git commit -m "feat(nav): add children support to navigation config"
```

---

### Task 2: Update AppSidebar to render collapsible sub-menus

**Files:**
- Modify: `frontend/src/components/layout/AppSidebar.tsx`

**Interfaces:**
- Consumes: `NavItem.children?: readonly NavChild[]` from Task 1
- Produces: sidebar renders `SidebarMenuSub` with `NavLink` children for items that have `children`

- [ ] **Step 1: Replace the contents of `frontend/src/components/layout/AppSidebar.tsx`**

```tsx
import { useState } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { ChevronUp, LogOut, User, ChevronDown } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { navigationItems } from '@/config/navigation'
import type { NavItem } from '@/config/navigation'
import { cn } from '@/lib/utils'
import { ProjectSwitcher } from '@/components/ProjectSwitcher'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from '@/components/ui/sidebar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import ragadminLogo from '@/assets/ragadmin-logo.png'

function getInitials(name?: string, email?: string): string {
  if (name) {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }
  if (email) {
    return email[0].toUpperCase()
  }
  return 'U'
}

function CollapsibleNavItem({ item, pathname }: { item: NavItem; pathname: string }) {
  const children = item.children!
  const isAnyChildActive = children.some((child) => pathname.startsWith(child.href))
  const [isOpen, setIsOpen] = useState(isAnyChildActive)

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        onClick={() => setIsOpen((o) => !o)}
        isActive={isAnyChildActive}
        tooltip={item.label}
        className={cn(
          isAnyChildActive && `border-l-[3px] ${item.activeColor}`,
          !isAnyChildActive && 'border-l-[3px] border-l-transparent'
        )}
      >
        <item.icon />
        <span>{item.label}</span>
        <ChevronDown
          className={cn('ml-auto h-4 w-4 transition-transform duration-200', isOpen && 'rotate-180')}
        />
      </SidebarMenuButton>
      {isOpen && (
        <SidebarMenuSub>
          {children.map((child) => {
            const isChildActive = pathname.startsWith(child.href)
            return (
              <SidebarMenuSubItem key={child.href}>
                <SidebarMenuSubButton asChild isActive={isChildActive}>
                  <NavLink to={child.href}>{child.label}</NavLink>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            )
          })}
        </SidebarMenuSub>
      )}
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSignOut = async () => {
    await signOut()
    navigate('/signin', { replace: true })
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex h-14 items-center gap-2 px-4 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <img
            src={ragadminLogo}
            alt="RAG Admin"
            className="h-8 w-8 shrink-0"
          />
          <h1 className="text-lg font-semibold text-primary group-data-[collapsible=icon]:hidden">
            RAG Admin
          </h1>
        </div>
        <ProjectSwitcher />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navigationItems.map((item) => {
                if (item.children) {
                  return (
                    <CollapsibleNavItem
                      key={item.label}
                      item={item}
                      pathname={location.pathname}
                    />
                  )
                }

                const isActive =
                  item.href === '/'
                    ? location.pathname === '/'
                    : location.pathname.startsWith(item.href)

                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={item.label}
                      className={cn(
                        isActive && `border-l-[3px] ${item.activeColor}`,
                        !isActive && 'border-l-[3px] border-l-transparent'
                      )}
                    >
                      <NavLink to={item.href}>
                        <item.icon />
                        <span>{item.label}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton className="h-auto py-2" tooltip={user?.fullName || user?.email || 'Account'}>
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>
                      {getInitials(
                        user?.fullName ?? undefined,
                        user?.email ?? undefined
                      )}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex flex-col items-start text-left">
                    <span className="text-sm font-medium">
                      {user?.fullName || user?.email}
                    </span>
                    {user?.fullName && (
                      <span className="text-xs text-muted-foreground">
                        {user.email}
                      </span>
                    )}
                  </div>
                  <ChevronUp className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="top"
                className="w-[--radix-popper-anchor-width]"
              >
                <DropdownMenuItem>
                  <User className="mr-2 h-4 w-4" />
                  <span>Profile</span>
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={handleSignOut}>
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>Log out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no new errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/AppSidebar.tsx
git commit -m "feat(nav): render collapsible sub-menus for nav items with children"
```

---

### Task 3: Create RetrievalEvaluationPage

**Files:**
- Create: `frontend/src/pages/RetrievalEvaluationPage.tsx`
- Create: `frontend/src/pages/RetrievalEvaluationPage.test.tsx`

**Interfaces:**
- Consumes: `useEvalRuns(projectId)`, `useExperiments(projectId)`, `useGoldenSets(projectId)` hooks; `EvalRunsTab`, `ExperimentsTab`, `GoldenSetsTab` components — all already used in EvaluationPage
- Produces: default export `RetrievalEvaluationPage` consumed by App.tsx in Task 5

- [ ] **Step 1: Write the failing test at `frontend/src/pages/RetrievalEvaluationPage.test.tsx`**

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RetrievalEvaluationPage from './RetrievalEvaluationPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test Project' } }),
}))

vi.mock('@/hooks/useEvalRuns', () => ({
  useEvalRuns: () => ({ runs: [], isLoading: false, deleteRun: vi.fn() }),
}))

vi.mock('@/hooks/useExperiments', () => ({
  useExperiments: () => ({
    experiments: [],
    isLoading: false,
    createExperiment: vi.fn(),
    deleteExperiment: vi.fn(),
  }),
}))

vi.mock('@/hooks/useGoldenSets', () => ({
  useGoldenSets: () => ({
    goldenSets: [],
    isLoading: false,
    createGoldenSet: vi.fn(),
    deleteGoldenSet: vi.fn(),
  }),
}))

describe('RetrievalEvaluationPage', () => {
  it('renders page heading and all three tabs', () => {
    render(
      <MemoryRouter>
        <RetrievalEvaluationPage />
      </MemoryRouter>
    )
    expect(screen.getByText('Retrieval Evaluation')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Runs' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Experiments' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Golden Sets' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/pages/RetrievalEvaluationPage.test.tsx
```

Expected: FAIL — `Cannot find module './RetrievalEvaluationPage'`

- [ ] **Step 3: Create `frontend/src/pages/RetrievalEvaluationPage.tsx`**

```tsx
import { useProject } from '@/contexts/ProjectContext'
import { useEvalRuns } from '@/hooks/useEvalRuns'
import { useGoldenSets } from '@/hooks/useGoldenSets'
import { useExperiments } from '@/hooks/useExperiments'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EvalRunsTab } from '@/components/evaluation/EvalRunsTab'
import { GoldenSetsTab } from '@/components/evaluation/GoldenSetsTab'
import { ExperimentsTab } from '@/components/evaluation/ExperimentsTab'

export default function RetrievalEvaluationPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { runs, isLoading: runsLoading, deleteRun } = useEvalRuns(projectId)
  const { experiments, isLoading: experimentsLoading, createExperiment, deleteExperiment } =
    useExperiments(projectId)
  const { goldenSets, isLoading: gsLoading, createGoldenSet, deleteGoldenSet } =
    useGoldenSets(projectId)

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage evaluations.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Retrieval Evaluation</h1>
        <p className="text-muted-foreground">
          Measure and compare retrieval quality using golden sets.
        </p>
      </div>
      <Tabs defaultValue="runs">
        <TabsList>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="experiments">Experiments</TabsTrigger>
          <TabsTrigger value="golden-sets">Golden Sets</TabsTrigger>
        </TabsList>
        <TabsContent value="runs" className="mt-4">
          <EvalRunsTab runs={runs} isLoading={runsLoading} onDelete={deleteRun} />
        </TabsContent>
        <TabsContent value="experiments" className="mt-4">
          <ExperimentsTab
            experiments={experiments}
            isLoading={experimentsLoading}
            onCreate={createExperiment}
            onDelete={deleteExperiment}
          />
        </TabsContent>
        <TabsContent value="golden-sets" className="mt-4">
          <GoldenSetsTab
            goldenSets={goldenSets}
            isLoading={gsLoading}
            onCreate={createGoldenSet}
            onDelete={deleteGoldenSet}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/pages/RetrievalEvaluationPage.test.tsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RetrievalEvaluationPage.tsx frontend/src/pages/RetrievalEvaluationPage.test.tsx
git commit -m "feat(eval): add RetrievalEvaluationPage"
```

---

### Task 4: Rework ExtractionEvaluationPage to include Ground Truth tab

**Files:**
- Modify: `frontend/src/pages/ExtractionEvaluationPage.tsx`
- Create: `frontend/src/pages/ExtractionEvaluationPage.test.tsx`

**Interfaces:**
- Consumes:
  - `ExtractionEvalRunsTab({ projectId: string })` from `@/components/extraction-eval/ExtractionEvalRunsTab`
  - `ExtractionGroundTruthTab({ projectId: string })` from `@/components/extraction-ground-truth/ExtractionGroundTruthTab`
- Produces: default export `ExtractionEvaluationPage` consumed by App.tsx in Task 5

- [ ] **Step 1: Write the failing test at `frontend/src/pages/ExtractionEvaluationPage.test.tsx`**

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ExtractionEvaluationPage from './ExtractionEvaluationPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test Project' } }),
}))

vi.mock('@/components/extraction-eval/ExtractionEvalRunsTab', () => ({
  ExtractionEvalRunsTab: () => <div>runs-tab</div>,
}))

vi.mock('@/components/extraction-ground-truth/ExtractionGroundTruthTab', () => ({
  ExtractionGroundTruthTab: () => <div>ground-truth-tab</div>,
}))

describe('ExtractionEvaluationPage', () => {
  it('renders page heading and both tabs', () => {
    render(
      <MemoryRouter>
        <ExtractionEvaluationPage />
      </MemoryRouter>
    )
    expect(screen.getByText('Extraction Evaluation')).toBeInTheDocument()
    expect(screen.getByText('Runs')).toBeInTheDocument()
    expect(screen.getByText('Ground Truth')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/pages/ExtractionEvaluationPage.test.tsx
```

Expected: FAIL — heading or Ground Truth tab not found (current page has neither)

- [ ] **Step 3: Replace the contents of `frontend/src/pages/ExtractionEvaluationPage.tsx`**

```tsx
import { useState } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { cn } from '@/lib/utils'
import { ExtractionEvalRunsTab } from '@/components/extraction-eval/ExtractionEvalRunsTab'
import { ExtractionGroundTruthTab } from '@/components/extraction-ground-truth/ExtractionGroundTruthTab'

type Tab = 'runs' | 'ground-truth'

export default function ExtractionEvaluationPage(): JSX.Element {
  const { currentProject } = useProject()
  const [activeTab, setActiveTab] = useState<Tab>('runs')

  if (!currentProject) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Select a project to manage extraction evaluation.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Extraction Evaluation</h1>
        <p className="text-muted-foreground">
          Measure extraction quality against ground truth.
        </p>
      </div>

      <div className="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
        <button
          onClick={() => setActiveTab('runs')}
          className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
            activeTab === 'runs' && 'bg-background text-foreground shadow-sm'
          )}
        >
          Runs
        </button>
        <button
          onClick={() => setActiveTab('ground-truth')}
          className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all',
            activeTab === 'ground-truth' && 'bg-background text-foreground shadow-sm'
          )}
        >
          Ground Truth
        </button>
      </div>

      <div className={activeTab !== 'runs' ? 'hidden' : undefined}>
        <ExtractionEvalRunsTab projectId={currentProject.id} />
      </div>

      <div className={activeTab !== 'ground-truth' ? 'hidden' : undefined}>
        <ExtractionGroundTruthTab projectId={currentProject.id} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/pages/ExtractionEvaluationPage.test.tsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ExtractionEvaluationPage.tsx frontend/src/pages/ExtractionEvaluationPage.test.tsx
git commit -m "feat(eval): rework ExtractionEvaluationPage with Runs + Ground Truth tabs"
```

---

### Task 5: Update routes and delete obsolete pages

**Files:**
- Modify: `frontend/src/App.tsx`
- Delete: `frontend/src/pages/EvaluationPage.tsx`
- Delete: `frontend/src/pages/ExtractionGroundTruthPage.tsx`

**Interfaces:**
- Consumes: `RetrievalEvaluationPage` (Task 3), `ExtractionEvaluationPage` (Task 4)

- [ ] **Step 1: Update imports and routes in `frontend/src/App.tsx`**

Replace the `EvaluationPage` import with the two new pages:

```tsx
// Remove this line:
import EvaluationPage from './pages/EvaluationPage'

// Add these two lines in its place:
import RetrievalEvaluationPage from './pages/RetrievalEvaluationPage'
import ExtractionEvaluationPage from './pages/ExtractionEvaluationPage'
```

Replace the evaluation route block (currently lines 156–160):

```tsx
// Remove:
{
  path: 'evaluation',
  element: <EvaluationPage />,
  handle: { breadcrumb: 'Evaluation' },
},

// Add:
{
  path: 'evaluation/retrieval',
  element: <RetrievalEvaluationPage />,
  handle: { breadcrumb: 'Retrieval Evaluation' },
},
{
  path: 'evaluation/extraction',
  element: <ExtractionEvaluationPage />,
  handle: { breadcrumb: 'Extraction Evaluation' },
},
```

All other evaluation child routes (`evaluation/golden-sets/:goldenSetId`, `evaluation/experiments/:experimentId`, `evaluation/runs/new`, `evaluation/runs/:runId`, `evaluation/runs/:runId/results/:resultId`, `evaluation/compare`) remain unchanged.

- [ ] **Step 2: Delete obsolete pages**

```bash
rm frontend/src/pages/EvaluationPage.tsx
rm frontend/src/pages/ExtractionGroundTruthPage.tsx
```

- [ ] **Step 3: Run TypeScript check and full test suite**

```bash
cd frontend && npx tsc --noEmit
cd frontend && npx vitest run
```

Expected: no type errors, all tests pass

- [ ] **Step 4: Run lint**

```bash
cd frontend && npm run lint
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git rm frontend/src/pages/EvaluationPage.tsx frontend/src/pages/ExtractionGroundTruthPage.tsx
git commit -m "feat(eval): split evaluation into retrieval and extraction pages, update routes"
```

---

## Self-Review

**Spec coverage:**
- ✅ `href: ''` on non-linked Evaluation parent → Task 1
- ✅ `children` array in nav config → Task 1
- ✅ `SidebarMenuSub` collapsible parent, starts open if child active → Task 2
- ✅ `/evaluation/retrieval` with Runs/Experiments/Golden Sets tabs → Task 3
- ✅ `/evaluation/extraction` with Runs + Ground Truth tabs → Task 4
- ✅ Remove `/evaluation` route, add two new routes → Task 5
- ✅ Delete `EvaluationPage.tsx` and `ExtractionGroundTruthPage.tsx` → Task 5
- ✅ All existing child routes unchanged → Task 5 (they are not touched)

**Placeholder scan:** None found.

**Type consistency:**
- `NavChild` defined in Task 1, consumed in Task 2 ✅
- `ExtractionEvalRunsTab({ projectId })` prop matches component signature ✅
- `ExtractionGroundTruthTab({ projectId })` prop matches component signature ✅
- `RetrievalEvaluationPage` default export consumed in Task 5 ✅
- `ExtractionEvaluationPage` default export consumed in Task 5 ✅
