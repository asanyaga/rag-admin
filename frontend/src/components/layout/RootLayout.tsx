import { Outlet } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { NavigationTracker } from '@/components/NavigationTracker'

export function RootLayout() {
  return (
    <>
      <NavigationTracker />
      <Outlet />
      <Toaster />
    </>
  )
}
