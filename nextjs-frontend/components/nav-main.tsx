"use client"

import { usePathname } from "next/navigation"
import { ChevronRight, type LucideIcon } from "lucide-react"

import { hasPermission, type UserPermissions } from "@/lib/permissions"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar"

function isSectionActive(pathname: string, item: { url: string; items?: { url: string }[] }): boolean {
  if (item.url !== "#" && (pathname === item.url || pathname.startsWith(item.url + "/"))) return true
  return (item.items ?? []).some((sub) => sub.url !== "#" && (pathname === sub.url || pathname.startsWith(sub.url + "/")))
}

function canSeeItem(me: UserPermissions | null, required?: string[]): boolean {
  if (!required?.length) return true
  return hasPermission(me, ...required)
}

export function NavMain({
  items,
  userMe = null,
}: {
  userMe?: UserPermissions | null
  items: {
    title: string
    url: string
    icon?: LucideIcon
    isActive?: boolean
    hasChildren?: boolean
    requiredPermissions?: string[]
    items?: {
      title: string
      url: string
      requiredPermissions?: string[]
    }[]
  }[]
}) {
  const pathname = usePathname()
  const visibleItems = items
    .filter((item) => canSeeItem(userMe, item.requiredPermissions))
    .map((item) => ({
      ...item,
      items: (item.items ?? []).filter((sub) =>
        canSeeItem(userMe, sub.requiredPermissions ?? item.requiredPermissions),
      ),
    }))
    .filter((item) => !item.hasChildren || (item.items?.length ?? 0) > 0)

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Application</SidebarGroupLabel>
      <SidebarMenu>
        {visibleItems.map((item) =>
          item.hasChildren ? (
            <Collapsible
              key={item.title}
              asChild
              defaultOpen={item.isActive ?? isSectionActive(pathname, item)}
              className="group/collapsible"
            >
              <SidebarMenuItem>
                <CollapsibleTrigger asChild>
                  <SidebarMenuButton tooltip={item.title} className="font-bold">
                    {item.icon && <item.icon />}
                    <span>{item.title}</span>
                    <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub>
                    {(item.items ?? []).map((subItem) => (
                      <SidebarMenuSubItem key={subItem.title}>
                        <SidebarMenuSubButton asChild>
                          <a href={subItem.url}>
                            <span>{subItem.title}</span>
                          </a>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    ))}
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>
          ) : (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton tooltip={item.title} asChild className="font-bold">
                <a href={item.url}>
                  {item.icon && <item.icon />}
                  <span>{item.title}</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )
        )}
      </SidebarMenu>
    </SidebarGroup>
  )
}
