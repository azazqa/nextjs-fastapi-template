import { House, Users, type LucideIcon } from "lucide-react"

export interface NavItem {
  title: string
  url: string
  icon?: LucideIcon
  isActive?: boolean
  hasChildren?: boolean
  /** Show when user has any of these permissions (or is superuser). */
  requiredPermissions?: string[]
  items?: { title: string; url: string; requiredPermissions?: string[] }[]
}

export const navMain: NavItem[] = [
  {
    title: "홈",
    url: "/",
    icon: House,
    hasChildren: false,
  },
  {
    title: "관리자",
    url: "#",
    icon: Users,
    hasChildren: true,
    requiredPermissions: ["scheduler:read"],
    items: [
      {
        title: "스케줄 관리",
        url: "/admin/scheduler",
        requiredPermissions: ["scheduler:read"],
      },
    ],
  },
]

export function getPageTitle(pathname: string): string {
  for (const item of navMain) {
    if (item.url !== "#" && item.url === pathname) return item.title
    if (item.items) {
      for (const sub of item.items) {
        if (sub.url !== "#" && sub.url === pathname) return sub.title
      }
    }
    if (item.url !== "#" && item.url !== "/" && pathname.startsWith(item.url + "/")) {
      return item.title
    }
  }
  return ""
}
