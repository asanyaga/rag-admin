# Default Project Refactor Plan

**Status**: Not Started
**Priority**: Medium
**Estimated Time**: ~2-3 hours
**Prerequisites**: Documents feature fully tested and working

---

## Overview

Refactor the application to use a "default project" pattern instead of requiring explicit project navigation. This improves UX by:
- Auto-creating a default project on signup
- Using a "current project" context
- Making Documents/Index/Experiments operate on the current project
- Adding a project switcher UI

---

## Current Architecture

```
User creates account
  ↓
User must create a project manually
  ↓
User navigates to /projects
  ↓
User clicks "View Documents" (doesn't exist yet)
  ↓
User navigates to /projects/{id}/documents
  ↓
User can upload documents
```

**Problems:**
- Extra friction (3+ steps to upload first document)
- Global Documents/Index navigation has no context
- Not clear which project you're working in

---

## Target Architecture

```
User creates account
  ↓
System auto-creates "My Documents" project
  ↓
User sees Documents/Index in main navigation
  ↓
Documents operates on current project (default initially)
  ↓
User can switch projects via dropdown
  ↓
All features respect current project context
```

**Benefits:**
- Immediate value (can use app right away)
- Simpler mental model
- Better for single-project users (majority)
- Scales to multi-project power users

---

## Implementation Phases

### Phase 1: Backend - Default Project Creation (30 min)

**Goal**: Auto-create default project when user signs up

#### 1.1 Add `is_default` Column to Projects
```sql
-- Migration
ALTER TABLE projects ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX ix_projects_user_default ON projects(user_id, is_default);
```

#### 1.2 Update User Creation Logic
```python
# app/services/auth_service.py or similar

async def create_user_with_default_project(...):
    # Create user
    user = await user_repo.create(...)

    # Create default project
    default_project = await project_repo.create(
        user_id=user.id,
        data=ProjectCreate(
            name="My Documents",
            description="Your personal document collection",
        )
    )

    # Mark as default
    await project_repo.set_as_default(user.id, default_project.id)

    return user
```

#### 1.3 Add Repository Methods
```python
# app/repositories/project_repository.py

async def get_default_project(self, user_id: UUID) -> Project | None:
    """Get user's default project."""
    result = await self.session.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.is_default == True
        )
    )
    return result.scalar_one_or_none()

async def set_as_default(self, user_id: UUID, project_id: UUID) -> None:
    """Set a project as the user's default."""
    # Clear existing default
    await self.session.execute(
        update(Project)
        .where(Project.user_id == user_id)
        .values(is_default=False)
    )

    # Set new default
    await self.session.execute(
        update(Project)
        .where(
            Project.user_id == user_id,
            Project.id == project_id
        )
        .values(is_default=True)
    )
    await self.session.commit()
```

#### 1.4 Add API Endpoint
```python
# app/routers/projects.py

@router.get("/default", response_model=ProjectResponse)
async def get_default_project(
    current_user: User = Depends(get_current_active_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get user's default project."""
    return await project_service.get_default_project(current_user.id)
```

---

### Phase 2: Frontend - Project Context (1 hour)

**Goal**: Create context to track and switch current project

#### 2.1 Create ProjectContext
```typescript
// src/contexts/ProjectContext.tsx

interface ProjectContextType {
  currentProject: Project | null
  setCurrentProject: (project: Project) => void
  projects: Project[]
  isLoading: boolean
  fetchProjects: () => Promise<void>
  createProject: (data: ProjectCreate) => Promise<Project>
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [currentProject, setCurrentProjectState] = useState<Project | null>(null)
  const [projects, setProjects] = useState<Project[]>([])

  // Load from localStorage on mount
  useEffect(() => {
    const savedProjectId = localStorage.getItem('currentProjectId')
    if (savedProjectId) {
      // Fetch and set project
    } else {
      // Fetch default project
      fetchDefaultProject()
    }
  }, [])

  const setCurrentProject = (project: Project) => {
    setCurrentProjectState(project)
    localStorage.setItem('currentProjectId', project.id)
  }

  const fetchDefaultProject = async () => {
    const defaultProject = await getDefaultProject()
    setCurrentProject(defaultProject)
  }

  return (
    <ProjectContext.Provider value={{
      currentProject,
      setCurrentProject,
      projects,
      isLoading,
      fetchProjects,
      createProject,
    }}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject() {
  const context = useContext(ProjectContext)
  if (!context) {
    throw new Error('useProject must be used within ProjectProvider')
  }
  return context
}
```

#### 2.2 Add to App
```typescript
// src/App.tsx

function App() {
  return (
    <AuthProvider>
      <ProjectProvider>
        <RouterProvider router={router} />
      </ProjectProvider>
    </AuthProvider>
  )
}
```

#### 2.3 Add API Function
```typescript
// src/api/projects.ts

export async function getDefaultProject(): Promise<Project> {
  const response = await apiClient.get<Project>('/projects/default')
  return response.data
}
```

---

### Phase 3: Frontend - Project Switcher UI (30 min)

**Goal**: Add UI to switch between projects

#### 3.1 Create ProjectSwitcher Component
```typescript
// src/components/ProjectSwitcher.tsx

export function ProjectSwitcher() {
  const { currentProject, projects, setCurrentProject } = useProject()
  const navigate = useNavigate()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="w-full justify-start">
          <FolderKanban className="mr-2 h-4 w-4" />
          <span className="truncate">{currentProject?.name || 'Select Project'}</span>
          <ChevronDown className="ml-auto h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel>Projects</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {projects.map((project) => (
          <DropdownMenuItem
            key={project.id}
            onClick={() => setCurrentProject(project)}
            className={project.id === currentProject?.id ? 'bg-accent' : ''}
          >
            <FolderKanban className="mr-2 h-4 w-4" />
            {project.name}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate('/projects')}>
          <Plus className="mr-2 h-4 w-4" />
          Manage Projects
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

#### 3.2 Add to Sidebar
```typescript
// src/components/layout/AppSidebar.tsx

export function AppSidebar() {
  return (
    <Sidebar>
      <SidebarHeader>
        <div className="px-2 py-2">
          <ProjectSwitcher />
        </div>
      </SidebarHeader>
      {/* ... rest of sidebar */}
    </Sidebar>
  )
}
```

---

### Phase 4: Frontend - Update Pages (30 min)

**Goal**: Update pages to use current project from context

#### 4.1 Update DocumentsPage
```typescript
// src/pages/DocumentsPage.tsx

export default function DocumentsPage() {
  const { currentProject } = useProject()

  const {
    documents,
    uploadDocument,
    // ...
  } = useDocuments(currentProject?.id || null)

  if (!currentProject) {
    return <div>Loading project...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Documents</h1>
          <p className="text-muted-foreground mt-1">
            {currentProject.name}
          </p>
        </div>
      </div>

      {/* Rest of page uses currentProject.id */}
    </div>
  )
}
```

#### 4.2 Update Routes
```typescript
// src/App.tsx

// Change from:
{
  path: 'projects/:projectId/documents',
  element: <ProjectDocumentsPage />,
}

// To:
{
  path: 'documents',
  element: <DocumentsPage />,
}
```

#### 4.3 Keep Projects Page for Management
```typescript
// Projects page becomes project management
// Not the main workflow, but available for:
// - Creating new projects
// - Switching projects
// - Archiving/deleting projects
```

---

### Phase 5: Testing & Migration (30 min)

#### 5.1 Test Flows

**New User Flow:**
1. Sign up
2. Verify default project created
3. Navigate to Documents
4. Upload document (should use default project)
5. Verify document appears

**Existing User Flow:**
1. Login with existing account (no default project)
2. System creates default project on first load
3. Migrate existing documents to default project (optional)

**Multi-Project Flow:**
1. Create second project via Projects page
2. Switch project via dropdown
3. Upload document to new project
4. Switch back to default
5. Verify documents are project-specific

#### 5.2 Migration Strategy

**For existing users without default project:**
```typescript
// On app load, check if user has default project
const defaultProject = await getDefaultProject()

if (!defaultProject) {
  // Auto-create default project
  const newDefault = await createProject({
    name: "My Documents",
    description: "Auto-created default project",
  })
  await setAsDefault(newDefault.id)
}
```

---

## Success Criteria

- ✅ New users get default project automatically
- ✅ Documents/Index operate on current project
- ✅ Project switcher works smoothly
- ✅ localStorage persists current project selection
- ✅ Existing functionality still works
- ✅ Can create and manage multiple projects
- ✅ No breaking changes to API
- ✅ All existing tests pass

---

## Rollback Plan

If issues arise:
1. Remove `is_default` column (backward compatible)
2. Revert to URL-based project context (`/projects/{id}/documents`)
3. Remove ProjectContext provider
4. Restore previous routing

---

## Future Enhancements

After this refactor is stable:

1. **Project Templates**
   - Pre-configured projects for common use cases
   - "Research Papers", "Legal Documents", etc.

2. **Project Sharing**
   - Share projects with other users
   - Collaborative document management

3. **Project Import/Export**
   - Export project data
   - Import from other systems

4. **Advanced Project Settings**
   - Custom indexing strategies per project
   - Project-specific embeddings models

---

## Notes

- This refactor doesn't change the backend data model significantly
- Documents still belong to projects (foreign key remains)
- Just changes how users interact with projects
- Can be done incrementally (backend → context → UI)
- Safe to test in isolation before rolling out

---

## Dependencies

- Requires: Documents feature fully implemented and tested
- Blocks: Index feature, Experiments feature
- Related: User onboarding flow

---

**Ready to implement in a future session after documents feature is validated.**
