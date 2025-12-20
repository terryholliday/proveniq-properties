'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { maintenanceApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  Plus, 
  Wrench, 
  Search,
  AlertTriangle,
  ChevronRight
} from 'lucide-react'

interface MaintenanceTicket {
  id: string
  unit_id: string
  title: string
  status: string
  priority: number
}

export default function MaintenancePage() {
  const { getIdToken } = useAuth()
  const [tickets, setTickets] = useState<MaintenanceTicket[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadTickets()
  }, [])

  const loadTickets = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await maintenanceApi.list(token)
      setTickets(data)
    } catch (error) {
      console.error('Failed to load tickets:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredTickets = tickets.filter((t) =>
    t.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

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
          <h1 className="text-2xl font-bold text-slate-900">Maintenance</h1>
          <p className="text-slate-600">{tickets.length} total tickets</p>
        </div>
        <Link href="/dashboard/maintenance/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Ticket
          </Button>
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
        <input
          type="text"
          placeholder="Search tickets..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
        />
      </div>

      {/* Tickets List */}
      {filteredTickets.length === 0 ? (
        <div className="bg-white rounded-xl border p-12 text-center">
          <Wrench className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">
            {searchQuery ? 'No tickets found' : 'No maintenance tickets'}
          </h3>
          <p className="text-slate-500 mb-6">
            {searchQuery ? 'Try a different search' : 'Create a ticket when maintenance is needed'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border divide-y">
          {filteredTickets.map((ticket) => (
            <Link
              key={ticket.id}
              href={`/dashboard/maintenance/${ticket.id}`}
              className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className={`p-2 rounded-lg ${getPriorityColor(ticket.priority)}`}>
                  {ticket.priority >= 4 ? (
                    <AlertTriangle className="h-5 w-5" />
                  ) : (
                    <Wrench className="h-5 w-5" />
                  )}
                </div>
                <div>
                  <p className="font-medium">{ticket.title}</p>
                  <p className="text-sm text-slate-500">Priority: {ticket.priority}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <StatusBadge status={ticket.status} />
                <ChevronRight className="h-5 w-5 text-slate-400" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function getPriorityColor(priority: number): string {
  if (priority >= 4) return 'bg-red-100 text-red-600'
  if (priority >= 3) return 'bg-amber-100 text-amber-600'
  return 'bg-slate-100 text-slate-600'
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    open: 'bg-blue-100 text-blue-600',
    assigned: 'bg-purple-100 text-purple-600',
    in_progress: 'bg-amber-100 text-amber-600',
    resolved: 'bg-green-100 text-green-600',
    closed: 'bg-slate-100 text-slate-600',
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-slate-100 text-slate-600'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
