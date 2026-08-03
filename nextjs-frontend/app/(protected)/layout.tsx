import { AppSidebar } from "@/components/app-sidebar"
import { PageTitle } from "@/components/page-title"
import { UserMenu } from "@/components/user-menu"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 border-b-2 border-indigo-700 shrink-0 items-center justify-between transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 px-4">
          <div className="flex items-center gap-2">
            <SidebarTrigger className="-ml-1" />
            <Separator
              orientation="vertical"
              className="mr-2"
            />
            <PageTitle />
          </div>
          <div className="flex items-center justify-end gap-2">
            <UserMenu />
          </div>
        </header>
        <div className="bg-gray-100 flex flex-1 flex-col gap-4 p-3">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
