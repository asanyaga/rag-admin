import { SidebarTrigger } from '@/components/ui/sidebar'
import { Breadcrumbs } from './Breadcrumbs'

export function TopNav() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background">
      <div className="flex h-14 items-center gap-4 px-4">
        <SidebarTrigger />
        <Breadcrumbs />
      </div>
    </header>
  )
}
