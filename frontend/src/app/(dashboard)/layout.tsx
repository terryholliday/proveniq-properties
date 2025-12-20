'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { 
  Building2, 
  LayoutDashboard, 
  Home, 
  FileCheck, 
  Wrench, 
  Users,
  Settings,
  LogOut,
  ChevronDown
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { user, loading, signOut } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  const handleSignOut = async () => {
    await signOut()
    router.push('/')
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top Navigation */}
      <header className="bg-white border-b sticky top-0 z-50">
        <div className="flex items-center justify-between px-4 h-16">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-2">
            <Building2 className="h-7 w-7 text-primary" />
            <span className="text-lg font-bold">PROVENIQ Properties</span>
          </Link>

          {/* User Menu */}
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-600">{user.email}</span>
            <Button variant="ghost" size="sm" onClick={handleSignOut}>
              <LogOut className="h-4 w-4 mr-2" />
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r min-h-[calc(100vh-4rem)] p-4">
          <nav className="space-y-1">
            <NavItem href="/dashboard" icon={<LayoutDashboard className="h-5 w-5" />}>
              Dashboard
            </NavItem>
            <NavItem href="/dashboard/properties" icon={<Home className="h-5 w-5" />}>
              Properties
            </NavItem>
            <NavItem href="/dashboard/inspections" icon={<FileCheck className="h-5 w-5" />}>
              Inspections
            </NavItem>
            <NavItem href="/dashboard/maintenance" icon={<Wrench className="h-5 w-5" />}>
              Maintenance
            </NavItem>
            <NavItem href="/dashboard/team" icon={<Users className="h-5 w-5" />}>
              Team
            </NavItem>
            
            <div className="pt-4 mt-4 border-t">
              <NavItem href="/dashboard/settings" icon={<Settings className="h-5 w-5" />}>
                Settings
              </NavItem>
            </div>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}

function NavItem({ 
  href, 
  icon, 
  children 
}: { 
  href: string
  icon: React.ReactNode
  children: React.ReactNode 
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-3 py-2 rounded-lg text-slate-700 hover:bg-slate-100 transition-colors"
    >
      {icon}
      <span className="font-medium">{children}</span>
    </Link>
  )
}
