import { Home, FolderKanban, FileText, Database, BarChart3, Settings } from 'lucide-react'

export const navigationItems = [
  { label: 'Home', href: '/', icon: Home },
  { label: 'Projects', href: '/projects', icon: FolderKanban },
  { label: 'Documents', href: '/documents', icon: FileText },
  { label: 'Index', href: '/index', icon: Database },
  { label: 'Evaluation', href: '/evaluation', icon: BarChart3 },
  { label: 'Settings', href: '/settings', icon: Settings },
] as const
