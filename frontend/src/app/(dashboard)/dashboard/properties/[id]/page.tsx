'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { propertiesApi, leasesApi, inspectionsApi } from '@/lib/api'
import { getAssetProfile } from '@/lib/core-client'
import { AssetProfile } from '@/lib/core-contracts'
import { UniversalDashboard } from '@/components/widgets/registry'
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
  ChevronRight,
  WifiOff
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

  // CORE STATE
  const [assetProfile, setAssetProfile] = useState<AssetProfile | null>(null)
  const [coreError, setCoreError] = useState<string | null>(null)

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

      // Parallel Fetch: Legacy Property/Units + Core Profile
      const [propertyData, unitsData, coreResult] = await Promise.allSettled([
        propertiesApi.get(propertyId, token),
        propertiesApi.listUnits(propertyId, token),
        getAssetProfile(propertyId)
      ])

      // Handle Legacy Data
      if (propertyData.status === 'fulfilled') setProperty(propertyData.value as Property)
      if (unitsData.status === 'fulfilled') setUnits(unitsData.value as Unit[])

      // Handle Core Data (Fail-Loud in Console, Graceful in UI)
      if (coreResult.status === 'fulfilled') {
        setAssetProfile(coreResult.value)
        setCoreError(null)
      } else {
        console.error("Core Fetch Failed:", coreResult.reason)
        setCoreError(coreResult.reason?.message || "Failed to load Asset Truth")
      }

    } catch (error) {
      console.error('Failed to load property context:', error)
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

  // Fallback if legacy property data is missing, we can try to render just the Core profile?
  // For now, if local property is missing, strictly show 404 as before.
  // Fallback if legacy property data is missing, we can try to render just the Core profile?
  // Allow render if we have EITHER property OR assetProfile (for Mock testing)
  if (!property && !assetProfile) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Property not found in Registry or Core</p>
        <Link href="/dashboard/properties">
          <Button variant="outline" className="mt-4">
            Back to Properties
          </Button>
        </Link>
      </div>
    )
  }

  // Derive Display Data
  const displayName = property?.name || `Asset ${propertyId}`;
  const displayAddress = property ? `${property.address_line1}, ${property.city}, ${property.state}` : "Address Unknown (Core Only)";

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
            <h1 className="text-2xl font-bold text-slate-900">{displayName}</h1>
            <div className="flex items-center gap-1 text-slate-500 mt-1">
              <MapPin className="h-4 w-4" />
              <span>{displayAddress}</span>
            </div>
            {/* Core ID Badge */}
            <div className="mt-2 text-xs font-mono text-slate-400 bg-slate-100 px-2 py-1 rounded inline-block">
              ASSET ID: {propertyId}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline">Edit Property</Button>
          </div>
        </div>
      </div>

      {/* CORE WIDGET DASHBOARD */}
      {coreError && (
        <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-center gap-3 text-amber-800">
          <WifiOff className="h-5 w-5" />
          <div>
            <p className="text-sm font-bold">Asset Truth Offline</p>
            <p className="text-xs">{coreError} - Check local Core service (3010)</p>
          </div>
        </div>
      )}

      {assetProfile && <UniversalDashboard widgets={assetProfile.widgets} />}

      {/* Property Management (Units) */}
      <div className="bg-white rounded-xl border">
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Units & Leases</h2>
            <span className="px-2 py-0.5 bg-slate-100 rounded-full text-xs font-medium text-slate-600">{units.length}</span>
          </div>
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
