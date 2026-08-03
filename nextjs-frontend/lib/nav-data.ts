import { House, type LucideIcon } from "lucide-react"

export interface NavItem {
  title: string
  url: string
  icon?: LucideIcon
  isActive?: boolean
  hasChildren?: boolean
  items?: { title: string; url: string }[]
}

export const navMain: NavItem[] = [
  {
    title: "홈",
    url: "/",
    icon: House,
    hasChildren: false,
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
