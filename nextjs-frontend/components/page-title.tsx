"use client"

import { usePathname } from "next/navigation"
import { getPageTitle } from "@/lib/nav-data"

export function PageTitle() {
  const pathname = usePathname()
  const title = getPageTitle(pathname)

  if (!title) return null

  return <h1 className="text-lg font-semibold">{title}</h1>
}
