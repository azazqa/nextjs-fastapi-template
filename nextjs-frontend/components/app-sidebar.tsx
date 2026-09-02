"use client"

import * as React from "react"
import { NavMain } from "@/components/nav-main"
import { navMain } from "@/lib/nav-data"
import type { UserPermissions } from "@/lib/permissions"
import {
  Sidebar,
  SidebarContent,
  SidebarRail,
} from "@/components/ui/sidebar"

export function AppSidebar({
  userMe = null,
  ...props
}: React.ComponentProps<typeof Sidebar> & { userMe?: UserPermissions | null }) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarContent>
        <NavMain items={navMain} userMe={userMe} />
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
