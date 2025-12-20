'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { propertiesApi, leasesApi, inspectionsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Loader2, FileCheck, Home, Calendar } from 'lucide-react'

interface Property {
  id: string
  name: string
}

interface Unit {
  id: string
  unit_number: string
}

interface Lease {
  id: string
  unit_id: string
  tenant_email: string
  status: string
}

export default function NewInspectionPage() {
  const { getIdToken } = useAuth()
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [dataLoading, setDataLoading] = useState(true)
  const [error, setError] = useState('')

  const [properties, setProperties] = useState<Property[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [leases, setLeases] = useState<Lease[]>([])

  const [selectedPropertyId, setSelectedPropertyId] = useState('')
  const [selectedUnitId, setSelectedUnitId] = useState('')
  const [selectedLeaseId, setSelectedLeaseId] = useState('')
  const [inspectionType, setInspectionType] = useState('move_in')
  const [inspectionDate, setInspectionDate] = useState(
    new Date().toISOString().split('T')[0]
  )

  useEffect(() => {
    loadProperties()
  }, [])

  useEffect(() => {
    if (selectedPropertyId) {
      loadUnits(selectedPropertyId)
    } else {
      setUnits([])
      setSelectedUnitId('')
    }
  }, [selectedPropertyId])

  useEffect(() => {
    if (selectedUnitId) {
      loadLeases(selectedUnitId)
    } else {
      setLeases([])
      setSelectedLeaseId('')
    }
  }, [selectedUnitId])

  const loadProperties = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await propertiesApi.list(token)
      setProperties(data)
    } catch (error) {
      console.error('Failed to load properties:', error)
    } finally {
      setDataLoading(false)
    }
  }

  const loadUnits = async (propertyId: string) => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await propertiesApi.listUnits(propertyId, token)
      setUnits(data)
    } catch (error) {
      console.error('Failed to load units:', error)
    }
  }

  const loadLeases = async (unitId: string) => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await leasesApi.list(token, unitId)
      setLeases(data.filter(l => l.status === 'active'))
    } catch (error) {
      console.error('Failed to load leases:', error)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const token = await getIdToken()
      if (!token) throw new Error('Not authenticated')

      if (!selectedLeaseId) {
        throw new Error('Please select a lease')
      }

      const result = await inspectionsApi.create(
        {
          lease_id: selectedLeaseId,
          inspection_type: inspectionType,
          inspection_date: inspectionDate,
        },
        token
      ) as { id: string }

      router.push(`/dashboard/inspections/${result.id}`)
    } catch (err: any) {
      setError(err.message || 'Failed to create inspection')
    } finally {
      setLoading(false)
    }
  }

  if (dataLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/dashboard/inspections"
          className="inline-flex items-center text-sm text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Inspections
        </Link>
        <h1 className="text-2xl font-bold text-slate-900">New Inspection</h1>
        <p className="text-slate-600">Create a new property inspection</p>
      </div>

      {/* Form */}
      <div className="bg-white rounded-xl border p-6">
        {error && (
          <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Inspection Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-3">
              Inspection Type
            </label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { value: 'move_in', label: 'Move-In' },
                { value: 'move_out', label: 'Move-Out' },
                { value: 'periodic', label: 'Periodic' },
                { value: 'turnover', label: 'Turnover' },
              ].map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setInspectionType(type.value)}
                  className={`p-3 border rounded-lg text-center transition-all ${
                    inspectionType === type.value
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <span className="text-sm font-medium">{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Property Selection */}
          <div>
            <label htmlFor="property" className="block text-sm font-medium text-slate-700 mb-1">
              Property
            </label>
            <select
              id="property"
              value={selectedPropertyId}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
              required
            >
              <option value="">Select a property</option>
              {properties.map((property) => (
                <option key={property.id} value={property.id}>
                  {property.name}
                </option>
              ))}
            </select>
          </div>

          {/* Unit Selection */}
          {selectedPropertyId && (
            <div>
              <label htmlFor="unit" className="block text-sm font-medium text-slate-700 mb-1">
                Unit
              </label>
              <select
                id="unit"
                value={selectedUnitId}
                onChange={(e) => setSelectedUnitId(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                required
              >
                <option value="">Select a unit</option>
                {units.map((unit) => (
                  <option key={unit.id} value={unit.id}>
                    Unit {unit.unit_number}
                  </option>
                ))}
              </select>
              {units.length === 0 && (
                <p className="text-sm text-amber-600 mt-1">
                  No units found. Add units to this property first.
                </p>
              )}
            </div>
          )}

          {/* Lease Selection */}
          {selectedUnitId && (
            <div>
              <label htmlFor="lease" className="block text-sm font-medium text-slate-700 mb-1">
                Lease
              </label>
              <select
                id="lease"
                value={selectedLeaseId}
                onChange={(e) => setSelectedLeaseId(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                required
              >
                <option value="">Select a lease</option>
                {leases.map((lease) => (
                  <option key={lease.id} value={lease.id}>
                    {lease.tenant_email}
                  </option>
                ))}
              </select>
              {leases.length === 0 && (
                <p className="text-sm text-amber-600 mt-1">
                  No active leases. Create a lease for this unit first.
                </p>
              )}
            </div>
          )}

          {/* Inspection Date */}
          <div>
            <label htmlFor="date" className="block text-sm font-medium text-slate-700 mb-1">
              Inspection Date
            </label>
            <input
              id="date"
              type="date"
              value={inspectionDate}
              onChange={(e) => setInspectionDate(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
              required
            />
          </div>

          {/* Submit */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t">
            <Link href="/dashboard/inspections">
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </Link>
            <Button type="submit" disabled={loading || !selectedLeaseId}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Inspection'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
