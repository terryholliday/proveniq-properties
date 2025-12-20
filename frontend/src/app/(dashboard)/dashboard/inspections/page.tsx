'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { inspectionsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  Plus, 
  FileCheck, 
  Search,
  Calendar,
  ChevronRight,
  Filter
} from 'lucide-react'

interface Inspection {
  id: string
  lease_id: string
  inspection_type: string
  status: string
  inspection_date: string
  content_hash?: string
}

export default function InspectionsPage() {
  const { getIdToken } = useAuth()
  const [inspections, setInspections] = useState<Inspection[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('')

  useEffect(() => {
    loadInspections()
  }, [])

  const loadInspections = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await inspectionsApi.list(token)
      setInspections(data)
    } catch (error) {
      console.error('Failed to load inspections:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredInspections = inspections.filter((i) => {
    const matchesSearch = i.inspection_type.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = !filterStatus || i.status === filterStatus
    return matchesSearch && matchesStatus
  })

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
          <h1 className="text-2xl font-bold text-slate-900">Inspections</h1>
          <p className="text-slate-600">{inspections.length} total inspections</p>
        </div>
        <Link href="/dashboard/inspections/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Inspection
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
          <input
            type="text"
            placeholder="Search inspections..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
          />
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
        >
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="in_progress">In Progress</option>
          <option value="submitted">Submitted</option>
          <option value="signed">Signed</option>
        </select>
      </div>

      {/* Inspections List */}
      {filteredInspections.length === 0 ? (
        <div className="bg-white rounded-xl border p-12 text-center">
          <FileCheck className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">
            {searchQuery || filterStatus ? 'No inspections found' : 'No inspections yet'}
          </h3>
          <p className="text-slate-500 mb-6">
            {searchQuery || filterStatus
              ? 'Try different filters'
              : 'Create your first inspection to get started'}
          </p>
          {!searchQuery && !filterStatus && (
            <Link href="/dashboard/inspections/new">
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                New Inspection
              </Button>
            </Link>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl border divide-y">
          {filteredInspections.map((inspection) => (
            <Link
              key={inspection.id}
              href={`/dashboard/inspections/${inspection.id}`}
              className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className={`p-2 rounded-lg ${getTypeColor(inspection.inspection_type)}`}>
                  <FileCheck className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-medium">{formatInspectionType(inspection.inspection_type)}</p>
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Calendar className="h-4 w-4" />
                    <span>{new Date(inspection.inspection_date).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <StatusBadge status={inspection.status} />
                {inspection.content_hash && (
                  <span className="text-xs text-slate-400 font-mono">
                    #{inspection.content_hash.slice(0, 8)}
                  </span>
                )}
                <ChevronRight className="h-5 w-5 text-slate-400" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function formatInspectionType(type: string): string {
  const types: Record<string, string> = {
    move_in: 'Move-In Inspection',
    move_out: 'Move-Out Inspection',
    periodic: 'Periodic Inspection',
    pre_lease: 'Pre-Lease Inspection',
    turnover: 'Turnover Inspection',
  }
  return types[type] || type.replace('_', ' ')
}

function getTypeColor(type: string): string {
  const colors: Record<string, string> = {
    move_in: 'bg-green-100 text-green-600',
    move_out: 'bg-amber-100 text-amber-600',
    periodic: 'bg-blue-100 text-blue-600',
    pre_lease: 'bg-purple-100 text-purple-600',
    turnover: 'bg-pink-100 text-pink-600',
  }
  return colors[type] || 'bg-slate-100 text-slate-600'
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    draft: 'bg-slate-100 text-slate-600',
    in_progress: 'bg-blue-100 text-blue-600',
    submitted: 'bg-amber-100 text-amber-600',
    signed: 'bg-green-100 text-green-600',
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-slate-100 text-slate-600'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
