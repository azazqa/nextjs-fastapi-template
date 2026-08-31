"use client"

import * as React from "react"
import { NavMain } from "@/components/nav-main"
import { navMain } from "@/lib/nav-data"
import {
  Sidebar,
  SidebarContent,
  SidebarRail,
} from "@/components/ui/sidebar"

export function AppSidebar({
  isSuperuser = false,
  ...props
}: React.ComponentProps<typeof Sidebar> & { isSuperuser?: boolean }) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarContent>
        <NavMain items={navMain} isSuperuser={isSuperuser} />
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
