# Task: Implement App Navigation (Sidebar + Top Nav)

## Objective
Create the navigation system for RAG Admin using shadcn/ui components:
1. A responsive sidebar following the shadcn sidebar block pattern
2. A top navigation bar with sidebar toggle and breadcrumbs

## Reference
- shadcn sidebar block (documentation-style navigation)
- See attached screenshots for visual reference

## Design Constraints
**IMPORTANT**: This task prioritizes structural correctness over visual creativity.

- Use shadcn component defaults WITHOUT customization
- Do NOT introduce custom typography, color palettes, or animations
- Do NOT deviate from shadcn's default styling (we will customize later)
- Follow shadcn conventions for spacing, borders, and interactive states
- The frontend-design skill's guidance toward "bold aesthetics" does NOT apply here

## Functional Requirements

### 1. Sidebar

#### Header
- App name: "RAG Admin"

#### Navigation Items
Each item should have an icon (use Lucide icons) and label:

| Label     | Icon suggestion |
|-----------|-----------------|
| Home      | Home            |
| Projects  | FolderKanban    |
| Documents | FileText        |
| Index     | Database        |
| Settings  | Settings        |

#### Profile Section (Sidebar Footer)
- User avatar + name + email display
- Chevron indicator for dropdown
- Dropdown menu items:
  - Profile
  - Log out

### 2. Top Navigation Bar

#### Layout
- Fixed/sticky at top of main content area (not overlapping sidebar)
- Full width of the content area

#### Elements (left to right)
1. **Sidebar Toggle Button**
   - Icon: PanelLeft (or similar)
   - Toggles sidebar visibility on both mobile and desktop
   
2. **Breadcrumb Navigation**
   - Separator: chevron (>)
   - Example: "Projects > Project Name" or "Settings"
   - Root level shows just the current section name
   - Use shadcn Breadcrumb component

#### Breadcrumb Behavior
- Automatically generated based on current route
- Clickable segments navigate to parent routes
- Current page (last segment) is not a link

### Technical Requirements
- Use the shadcn MCP to fetch/install required components
- Components likely needed:
  - Sidebar: Sidebar, SidebarHeader, SidebarContent, SidebarFooter, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarTrigger, SidebarProvider
  - Top Nav: Breadcrumb, BreadcrumbList, BreadcrumbItem, BreadcrumbLink, BreadcrumbSeparator, BreadcrumbPage
  - Shared: Button, Avatar, DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, Separator
- Lucide React for icons
- Responsive: sidebar collapsible on mobile, persistent on desktop
- Current route should show active state in sidebar
- Use React Router (NavLink, useLocation, useMatches or similar) for navigation and breadcrumb generation

### Layout Structure
```
┌─────────────────────────────────────────────────┐
│ Sidebar │ Top Nav (toggle + breadcrumbs)        │
│         ├───────────────────────────────────────│
│ Header  │                                       │
│         │                                       │
│ Nav     │         Main Content Area             │
│ Items   │         (Outlet)                      │
│         │                                       │
│         │                                       │
│ Profile │                                       │
└─────────────────────────────────────────────────┘
```

## Out of Scope
- Search functionality
- Actual page content (just render an Outlet placeholder)
- Dark mode toggle
- Custom theming or styling beyond shadcn defaults

```

## Verification
- [ ] Sidebar renders with all 5 navigation items (Home, Projects, Documents, Index, Settings)
- [ ] Each nav item displays icon + label
- [ ] Active link state works correctly based on current route
- [ ] Profile section shows avatar, name, and email
- [ ] Profile dropdown opens with Profile and Log out options
- [ ] Top nav bar displays sidebar toggle button
- [ ] Top nav bar displays breadcrumbs reflecting current route
- [ ] Sidebar toggle button shows/hides sidebar
- [ ] Mobile: sidebar collapses to overlay/drawer mode
- [ ] Desktop: sidebar toggle works (collapse to icons or fully hide)
- [ ] All components use shadcn defaults (no custom CSS overrides)
- [ ] No TypeScript errors


## Notes
This establishes the navigation shell. Styling customization will be a separate future task once the app functionality is complete.