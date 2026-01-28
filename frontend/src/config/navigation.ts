import { Home, FolderKanban, FileText, Database, Settings } from 'lucide-react'

export const navigationItems = [
  { label: 'Home', href: '/', icon: Home },
  { label: 'Projects', href: '/projects', icon: FolderKanban },
  { label: 'Documents', href: '/documents', icon: FileText },
  { label: 'Index', href: '/index', icon: Database },
  { label: 'Settings', href: '/settings', icon: Settings },
] as const
