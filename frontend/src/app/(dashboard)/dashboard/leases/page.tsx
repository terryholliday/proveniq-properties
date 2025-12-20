'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { 
  FileText, 
  Plus, 
  Search, 
  Calendar,
  Home,
  User,
  DollarSign,
  ArrowRight,
  CheckCircle,
  Clock,
  XCircle
} from 'lucide-react'

interface Lease {
  id: string
  unit_id: string
  unit_number: string
  property_name: string
  tenant_name: string
  tenant_email: string
  start_date: string
  end_date: string
  rent_cents: number
  deposit_cents: number
  status: 'active' | 'pending' | 'ended'
  occupancy_model: string
  has_move_in_inspection: boolean
  has_move_out_inspection: boolean
}

const statusColors = {
  active: 'bg-green-100 text-green-800',
  pending: 'bg-yellow-100 text-yellow-800',
  ended: 'bg-slate-100 text-slate-800',
}

const statusIcons = {
  active: CheckCircle,
  pending: Clock,
  ended: XCircle,
}

export default function LeasesPage() {
  const { getIdToken } = useAuth()
  const [leases, setLeases] = useState<Lease[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  useEffect(() => {
    fetchLeases()
  }, [])

  const fetchLeases = async () => {
    try {
      const token = await getIdToken()
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/leases`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      if (response.ok) {
        const data = await response.json()
        setLeases(data.leases || [])
      }
    } catch (error) {
      console.error('Failed to fetch leases:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredLeases = leases.filter(lease => {
    const matchesSearch = 
      lease.tenant_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lease.property_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lease.unit_number?.toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesStatus = statusFilter === 'all' || lease.status === statusFilter
    
    return matchesSearch && matchesStatus
  })

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100)
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  // Stats
  const activeLeases = leases.filter(l => l.status === 'active').length
  const totalMonthlyRent = leases
    .filter(l => l.status === 'active')
    .reduce((sum, l) => sum + l.rent_cents, 0)

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
          <h1 className="text-2xl font-bold">Leases</h1>
          <p className="text-slate-600">Manage tenant leases and agreements</p>
        </div>
        <Link href="/dashboard/leases/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Lease
          </Button>
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Active Leases</p>
              <p className="text-2xl font-bold">{activeLeases}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <DollarSign className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Monthly Rent</p>
              <p className="text-2xl font-bold">{formatCurrency(totalMonthlyRent)}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <FileText className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Total Leases</p>
              <p className="text-2xl font-bold">{leases.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search by tenant, property, or unit..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-2">
          {['all', 'active', 'pending', 'ended'].map((status) => (
            <Button
              key={status}
              variant={statusFilter === status ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(status)}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Button>
          ))}
        </div>
      </div>

      {/* Leases List */}
      {filteredLeases.length === 0 ? (
        <div className="bg-white rounded-lg border p-8 text-center">
          <FileText className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No leases found</h3>
          <p className="text-slate-600 mb-4">
            {searchQuery || statusFilter !== 'all' 
              ? 'Try adjusting your filters'
              : 'Get started by creating your first lease'}
          </p>
          {!searchQuery && statusFilter === 'all' && (
            <Link href="/dashboard/leases/new">
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Lease
              </Button>
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredLeases.map((lease) => {
            const StatusIcon = statusIcons[lease.status]
            
            return (
              <Link key={lease.id} href={`/dashboard/leases/${lease.id}`}>
                <div className="bg-white rounded-lg border p-4 hover:border-primary transition-colors cursor-pointer">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="p-2 bg-slate-100 rounded-lg">
                        <Home className="h-5 w-5 text-slate-600" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium">{lease.property_name}</h3>
                          <span className="text-slate-400">•</span>
                          <span className="text-slate-600">Unit {lease.unit_number}</span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-slate-600">
                          <span className="flex items-center gap-1">
                            <User className="h-4 w-4" />
                            {lease.tenant_name || 'No tenant assigned'}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="h-4 w-4" />
                            {formatDate(lease.start_date)} - {formatDate(lease.end_date)}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="font-medium">{formatCurrency(lease.rent_cents)}/mo</p>
                        <p className="text-sm text-slate-600">
                          Deposit: {formatCurrency(lease.deposit_cents)}
                        </p>
                      </div>
                      
                      <span className={`px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${statusColors[lease.status]}`}>
                        <StatusIcon className="h-3 w-3" />
                        {lease.status}
                      </span>
                      
                      <ArrowRight className="h-5 w-5 text-slate-400" />
                    </div>
                  </div>
                  
                  {/* Inspection Status */}
                  <div className="flex gap-4 mt-3 pt-3 border-t">
                    <div className={`flex items-center gap-1 text-xs ${lease.has_move_in_inspection ? 'text-green-600' : 'text-slate-400'}`}>
                      <CheckCircle className="h-3 w-3" />
                      Move-in Inspection
                    </div>
                    <div className={`flex items-center gap-1 text-xs ${lease.has_move_out_inspection ? 'text-green-600' : 'text-slate-400'}`}>
                      <CheckCircle className="h-3 w-3" />
                      Move-out Inspection
                    </div>
                    {lease.has_move_in_inspection && lease.has_move_out_inspection && (
                      <span className="text-xs text-blue-600 font-medium ml-auto">
                        View Damage Diff →
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
