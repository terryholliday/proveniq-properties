'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { turnoversApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  Plus, 
  Sparkles,
  Search,
  Calendar,
  ChevronRight,
  Clock,
  CheckCircle,
  AlertTriangle,
  User
} from 'lucide-react'

interface Turnover {
  id: string
  unit_id: string
  scheduled_date: string
  due_by: string | null
  status: string
  started_at: string | null
  completed_at: string | null
  photos_complete: boolean
  has_damage: boolean
  needs_restock: boolean
}

export default function TurnoversPage() {
  const { getIdToken } = useAuth()
  const [turnovers, setTurnovers] = useState<Turnover[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string>('')

  useEffect(() => {
    loadTurnovers()
  }, [filterStatus])

  const loadTurnovers = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await turnoversApi.list(token, {
        status: filterStatus || undefined,
      })
      setTurnovers(data)
    } catch (error) {
      console.error('Failed to load turnovers:', error)
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

  const pendingCount = turnovers.filter(t => t.status === 'pending').length
  const inProgressCount = turnovers.filter(t => t.status === 'in_progress').length
  const completedCount = turnovers.filter(t => t.status === 'completed' || t.status === 'verified').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Turnovers</h1>
          <p className="text-slate-600">STR cleaning & turnover management</p>
        </div>
        <Link href="/dashboard/turnovers/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Schedule Turnover
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 rounded-lg text-amber-600">
              <Clock className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">{pendingCount}</p>
              <p className="text-sm text-slate-500">Pending</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">{inProgressCount}</p>
              <p className="text-sm text-slate-500">In Progress</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg text-green-600">
              <CheckCircle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">{completedCount}</p>
              <p className="text-sm text-slate-500">Completed</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-4">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
        >
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="verified">Verified</option>
          <option value="flagged">Flagged</option>
        </select>
      </div>

      {/* Turnovers List */}
      {turnovers.length === 0 ? (
        <div className="bg-white rounded-xl border p-12 text-center">
          <Sparkles className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">No turnovers yet</h3>
          <p className="text-slate-500 mb-6">Schedule your first turnover to get started</p>
          <Link href="/dashboard/turnovers/new">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Schedule Turnover
            </Button>
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border divide-y">
          {turnovers.map((turnover) => (
            <Link
              key={turnover.id}
              href={`/dashboard/turnovers/${turnover.id}`}
              className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className={`p-2 rounded-lg ${getStatusColor(turnover.status)}`}>
                  {getStatusIcon(turnover.status)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium">
                      {new Date(turnover.scheduled_date).toLocaleDateString()}
                    </p>
                    {turnover.has_damage && (
                      <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">Damage</span>
                    )}
                    {turnover.needs_restock && (
                      <span className="text-xs bg-amber-100 text-amber-600 px-2 py-0.5 rounded">Restock</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Calendar className="h-4 w-4" />
                    <span>
                      {turnover.due_by 
                        ? `Due by ${new Date(turnover.due_by).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                        : 'No deadline'}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <StatusBadge status={turnover.status} />
                  <p className="text-xs text-slate-500 mt-1">
                    {turnover.photos_complete ? '5/5 photos' : 'Photos pending'}
                  </p>
                </div>
                <ChevronRight className="h-5 w-5 text-slate-400" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-600',
    in_progress: 'bg-blue-100 text-blue-600',
    completed: 'bg-green-100 text-green-600',
    verified: 'bg-emerald-100 text-emerald-600',
    flagged: 'bg-red-100 text-red-600',
  }
  return colors[status] || 'bg-slate-100 text-slate-600'
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'pending':
      return <Clock className="h-5 w-5" />
    case 'in_progress':
      return <Sparkles className="h-5 w-5" />
    case 'completed':
    case 'verified':
      return <CheckCircle className="h-5 w-5" />
    case 'flagged':
      return <AlertTriangle className="h-5 w-5" />
    default:
      return <Clock className="h-5 w-5" />
  }
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-600',
    in_progress: 'bg-blue-100 text-blue-600',
    completed: 'bg-green-100 text-green-600',
    verified: 'bg-emerald-100 text-emerald-600',
    flagged: 'bg-red-100 text-red-600',
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-slate-100 text-slate-600'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
