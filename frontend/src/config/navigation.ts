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
  Library,
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
  { label: 'Source Documents', href: '/source-documents', icon: Library, activeColor: 'border-l-indigo-500' },
  { label: 'Parse', href: '/parse', icon: FileText, activeColor: 'border-l-blue-500' },
  { label: 'Classify', href: '/classify', icon: Tags, activeColor: 'border-l-pink-500' },
  { label: 'Extract', href: '/extract', icon: FileSearch, activeColor: 'border-l-orange-500' },
  { label: 'Index', href: '/index', icon: Database, activeColor: 'border-l-teal-500' },
  { label: 'Data Stores', href: '/data-stores', icon: HardDrive, activeColor: 'border-l-cyan-500' },
  { label: 'Export', href: '/export', icon: ArrowUpFromLine, activeColor: 'border-l-emerald-500' },
  { label: 'Agents', href: '/agent', icon: Bot, activeColor: 'border-l-purple-500' },
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
  { label: 'Settings', href: '/settings', icon: Settings, activeColor: 'border-l-gray-400' },
]
