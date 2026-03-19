import { LayoutDashboard, FolderKanban, FileText, Database, BarChart3, Settings, FileSearch } from 'lucide-react'

export const navigationItems = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard, activeColor: 'border-l-primary' },
  { label: 'Projects', href: '/projects', icon: FolderKanban, activeColor: 'border-l-violet-500' },
  { label: 'Documents', href: '/documents', icon: FileText, activeColor: 'border-l-blue-500' },
  { label: 'Index', href: '/index', icon: Database, activeColor: 'border-l-teal-500' },
  { label: 'Extraction', href: '/extraction', icon: FileSearch, activeColor: 'border-l-orange-500' },
  { label: 'Evaluation', href: '/evaluation', icon: BarChart3, activeColor: 'border-l-amber-500' },
  { label: 'Settings', href: '/settings', icon: Settings, activeColor: 'border-l-gray-400' },
] as const
