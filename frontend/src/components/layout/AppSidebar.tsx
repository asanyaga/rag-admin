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
