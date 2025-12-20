'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { propertiesApi, leasesApi, inspectionsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  ArrowLeft, 
  Plus, 
  Home, 
  FileCheck, 
  Users,
  MapPin,
  Building2,
  MoreVertical,
  ChevronRight
} from 'lucide-react'

interface Property {
  id: string
  name: string
  property_type: string
  address_line1: string
  city: string
  state: string
  zip_code: string
}

interface Unit {
  id: string
  unit_number: string
  status: string
  sq_ft?: number
}

export default function PropertyDetailPage() {
  const params = useParams()
  const propertyId = params.id as string
  const { getIdToken } = useAuth()
  
  const [property, setProperty] = useState<Property | null>(null)
  const [units, setUnits] = useState<Unit[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddUnit, setShowAddUnit] = useState(false)
  const [newUnitNumber, setNewUnitNumber] = useState('')
  const [newUnitSqFt, setNewUnitSqFt] = useState('')

  useEffect(() => {
    loadPropertyData()
  }, [propertyId])

  const loadPropertyData = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const [propertyData, unitsData] = await Promise.all([
        propertiesApi.get(propertyId, token),
        propertiesApi.listUnits(propertyId, token),
      ])

      setProperty(propertyData as Property)
      setUnits(unitsData)
    } catch (error) {
      console.error('Failed to load property:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddUnit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const token = await getIdToken()
      if (!token) return

      await propertiesApi.createUnit(
        propertyId,
        {
          unit_number: newUnitNumber,
          sq_ft: newUnitSqFt ? parseInt(newUnitSqFt) : undefined,
        },
        token
      )

      setNewUnitNumber('')
      setNewUnitSqFt('')
      setShowAddUnit(false)
      loadPropertyData()
    } catch (error) {
      console.error('Failed to add unit:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!property) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Property not found</p>
        <Link href="/dashboard/properties">
          <Button variant="outline" className="mt-4">
            Back to Properties
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/dashboard/properties"
          className="inline-flex items-center text-sm text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Properties
        </Link>
        
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{property.name}</h1>
            <div className="flex items-center gap-1 text-slate-500 mt-1">
              <MapPin className="h-4 w-4" />
              <span>{property.address_line1}, {property.city}, {property.state}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline">Edit Property</Button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
              <Home className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">{units.length}</p>
              <p className="text-sm text-slate-500">Total Units</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg text-green-600">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">{units.filter(u => u.status === 'occupied').length}</p>
              <p className="text-sm text-slate-500">Occupied</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 rounded-lg text-amber-600">
              <Home className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">{units.filter(u => u.status === 'vacant').length}</p>
              <p className="text-sm text-slate-500">Vacant</p>
            </div>
          </div>
        </div>
      </div>

      {/* Units */}
      <div className="bg-white rounded-xl border">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-lg font-semibold">Units</h2>
          <Button size="sm" onClick={() => setShowAddUnit(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Unit
          </Button>
        </div>

        {/* Add Unit Form */}
        {showAddUnit && (
          <div className="p-6 border-b bg-slate-50">
            <form onSubmit={handleAddUnit} className="flex items-end gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Unit Number
                </label>
                <input
                  type="text"
                  value={newUnitNumber}
                  onChange={(e) => setNewUnitNumber(e.target.value)}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                  placeholder="e.g., 101"
                  required
                />
              </div>
              <div className="w-32">
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Sq Ft
                </label>
                <input
                  type="number"
                  value={newUnitSqFt}
                  onChange={(e) => setNewUnitSqFt(e.target.value)}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                  placeholder="850"
                />
              </div>
              <Button type="submit">Add</Button>
              <Button type="button" variant="outline" onClick={() => setShowAddUnit(false)}>
                Cancel
              </Button>
            </form>
          </div>
        )}

        {/* Units List */}
        {units.length === 0 ? (
          <div className="p-12 text-center">
            <Home className="h-12 w-12 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">No units yet</h3>
            <p className="text-slate-500 mb-4">Add units to start managing leases and inspections</p>
            <Button onClick={() => setShowAddUnit(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add First Unit
            </Button>
          </div>
        ) : (
          <div className="divide-y">
            {units.map((unit) => (
              <Link
                key={unit.id}
                href={`/dashboard/properties/${propertyId}/units/${unit.id}`}
                className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-slate-100 rounded-lg">
                    <Home className="h-5 w-5 text-slate-600" />
                  </div>
                  <div>
                    <p className="font-medium">Unit {unit.unit_number}</p>
                    {unit.sq_ft && (
                      <p className="text-sm text-slate-500">{unit.sq_ft} sq ft</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <StatusBadge status={unit.status} />
                  <ChevronRight className="h-5 w-5 text-slate-400" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    vacant: 'bg-amber-100 text-amber-600',
    occupied: 'bg-green-100 text-green-600',
    maintenance: 'bg-red-100 text-red-600',
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || 'bg-slate-100 text-slate-600'}`}>
      {status}
    </span>
  )
}
