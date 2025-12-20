'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { propertiesApi, inspectionsApi, maintenanceApi, orgApi } from '@/lib/api'
import { 
  Building2, 
  Home, 
  FileCheck, 
  Wrench, 
  AlertTriangle,
  Plus,
  ArrowRight,
  Clock
} from 'lucide-react'
import { Button } from '@/components/ui/button'

interface DashboardStats {
  propertyCount: number
  unitCount: number
  pendingInspections: number
  openTickets: number
  orgName: string
}

export default function DashboardPage() {
  const { getIdToken } = useAuth()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [recentInspections, setRecentInspections] = useState<any[]>([])
  const [recentTickets, setRecentTickets] = useState<any[]>([])

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const [org, properties, inspections, tickets] = await Promise.all([
        orgApi.getMyOrg(token),
        propertiesApi.list(token),
        inspectionsApi.list(token),
        maintenanceApi.list(token),
      ])

      const unitCount = properties.reduce((sum, p) => sum + (p.unit_count || 0), 0)
      const pendingInspections = inspections.filter(i => i.status === 'draft' || i.status === 'in_progress').length
      const openTickets = tickets.filter(t => t.status !== 'closed' && t.status !== 'resolved').length

      setStats({
        propertyCount: properties.length,
        unitCount,
        pendingInspections,
        openTickets,
        orgName: org.name,
      })

      setRecentInspections(inspections.slice(0, 5))
      setRecentTickets(tickets.slice(0, 5))
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-600">{stats?.orgName || 'Your Organization'}</p>
        </div>
        <Link href="/dashboard/properties/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Property
          </Button>
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Building2 className="h-6 w-6" />}
          label="Properties"
          value={stats?.propertyCount || 0}
          href="/dashboard/properties"
        />
        <StatCard
          icon={<Home className="h-6 w-6" />}
          label="Total Units"
          value={stats?.unitCount || 0}
          href="/dashboard/properties"
        />
        <StatCard
          icon={<FileCheck className="h-6 w-6" />}
          label="Pending Inspections"
          value={stats?.pendingInspections || 0}
          href="/dashboard/inspections"
          highlight={stats?.pendingInspections ? stats.pendingInspections > 0 : false}
        />
        <StatCard
          icon={<Wrench className="h-6 w-6" />}
          label="Open Tickets"
          value={stats?.openTickets || 0}
          href="/dashboard/maintenance"
          highlight={stats?.openTickets ? stats.openTickets > 0 : false}
        />
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <QuickAction
            href="/dashboard/properties/new"
            icon={<Building2 className="h-5 w-5" />}
            title="Add Property"
            description="Create a new property"
          />
          <QuickAction
            href="/dashboard/inspections/new"
            icon={<FileCheck className="h-5 w-5" />}
            title="Start Inspection"
            description="Begin a new inspection"
          />
          <QuickAction
            href="/dashboard/maintenance/new"
            icon={<Wrench className="h-5 w-5" />}
            title="Create Ticket"
            description="Log maintenance request"
          />
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Inspections */}
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Recent Inspections</h2>
            <Link href="/dashboard/inspections" className="text-primary text-sm font-medium hover:underline">
              View all
            </Link>
          </div>
          {recentInspections.length === 0 ? (
            <p className="text-slate-500 text-center py-8">No inspections yet</p>
          ) : (
            <div className="space-y-3">
              {recentInspections.map((inspection) => (
                <div key={inspection.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <FileCheck className="h-5 w-5 text-slate-400" />
                    <div>
                      <p className="font-medium text-sm">{inspection.inspection_type}</p>
                      <p className="text-xs text-slate-500">{inspection.inspection_date}</p>
                    </div>
                  </div>
                  <StatusBadge status={inspection.status} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Tickets */}
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Recent Maintenance</h2>
            <Link href="/dashboard/maintenance" className="text-primary text-sm font-medium hover:underline">
              View all
            </Link>
          </div>
          {recentTickets.length === 0 ? (
            <p className="text-slate-500 text-center py-8">No maintenance tickets yet</p>
          ) : (
            <div className="space-y-3">
              {recentTickets.map((ticket) => (
                <div key={ticket.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <Wrench className="h-5 w-5 text-slate-400" />
                    <div>
                      <p className="font-medium text-sm">{ticket.title}</p>
                      <p className="text-xs text-slate-500">Priority: {ticket.priority}</p>
                    </div>
                  </div>
                  <StatusBadge status={ticket.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ 
  icon, 
  label, 
  value, 
  href,
  highlight = false
}: { 
  icon: React.ReactNode
  label: string
  value: number
  href: string
  highlight?: boolean
}) {
  return (
    <Link href={href}>
      <div className={`bg-white rounded-xl border p-6 hover:shadow-md transition-shadow ${highlight ? 'border-amber-300 bg-amber-50' : ''}`}>
        <div className="flex items-center justify-between">
          <div className={`p-2 rounded-lg ${highlight ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-600'}`}>
            {icon}
          </div>
          <ArrowRight className="h-4 w-4 text-slate-400" />
        </div>
        <div className="mt-4">
          <p className="text-3xl font-bold text-slate-900">{value}</p>
          <p className="text-sm text-slate-600">{label}</p>
        </div>
      </div>
    </Link>
  )
}

function QuickAction({
  href,
  icon,
  title,
  description,
}: {
  href: string
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <Link href={href}>
      <div className="flex items-center gap-4 p-4 border rounded-lg hover:bg-slate-50 transition-colors">
        <div className="p-2 bg-primary/10 rounded-lg text-primary">
          {icon}
        </div>
        <div>
          <p className="font-medium">{title}</p>
          <p className="text-sm text-slate-500">{description}</p>
        </div>
      </div>
    </Link>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    draft: 'bg-slate-100 text-slate-600',
    in_progress: 'bg-blue-100 text-blue-600',
    submitted: 'bg-amber-100 text-amber-600',
    signed: 'bg-green-100 text-green-600',
    open: 'bg-blue-100 text-blue-600',
    assigned: 'bg-purple-100 text-purple-600',
    resolved: 'bg-green-100 text-green-600',
    closed: 'bg-slate-100 text-slate-600',
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-slate-100 text-slate-600'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
