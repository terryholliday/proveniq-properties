'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { propertiesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  Plus, 
  Building2, 
  Home, 
  MapPin, 
  Search,
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
  unit_count: number
}

export default function PropertiesPage() {
  const { getIdToken } = useAuth()
  const [properties, setProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadProperties()
  }, [])

  const loadProperties = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await propertiesApi.list(token)
      setProperties(data)
    } catch (error) {
      console.error('Failed to load properties:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredProperties = properties.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.address_line1.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.city.toLowerCase().includes(searchQuery.toLowerCase())
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
          <h1 className="text-2xl font-bold text-slate-900">Properties</h1>
          <p className="text-slate-600">{properties.length} properties</p>
        </div>
        <Link href="/dashboard/properties/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Property
          </Button>
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
        <input
          type="text"
          placeholder="Search properties..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
        />
      </div>

      {/* Properties Grid */}
      {filteredProperties.length === 0 ? (
        <div className="bg-white rounded-xl border p-12 text-center">
          <Building2 className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">
            {searchQuery ? 'No properties found' : 'No properties yet'}
          </h3>
          <p className="text-slate-500 mb-6">
            {searchQuery
              ? 'Try a different search term'
              : 'Add your first property to get started'}
          </p>
          {!searchQuery && (
            <Link href="/dashboard/properties/new">
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Property
              </Button>
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredProperties.map((property) => (
            <PropertyCard key={property.id} property={property} />
          ))}
        </div>
      )}
    </div>
  )
}

function PropertyCard({ property }: { property: Property }) {
  const typeIcons: Record<string, React.ReactNode> = {
    residential: <Home className="h-5 w-5" />,
    commercial: <Building2 className="h-5 w-5" />,
    mixed: <Building2 className="h-5 w-5" />,
  }

  const typeColors: Record<string, string> = {
    residential: 'bg-blue-100 text-blue-600',
    commercial: 'bg-purple-100 text-purple-600',
    mixed: 'bg-amber-100 text-amber-600',
  }

  return (
    <Link href={`/dashboard/properties/${property.id}`}>
      <div className="bg-white rounded-xl border p-6 hover:shadow-md transition-shadow cursor-pointer">
        <div className="flex items-start justify-between mb-4">
          <div className={`p-2 rounded-lg ${typeColors[property.property_type] || 'bg-slate-100 text-slate-600'}`}>
            {typeIcons[property.property_type] || <Building2 className="h-5 w-5" />}
          </div>
          <span className="text-xs font-medium text-slate-500 uppercase">
            {property.property_type}
          </span>
        </div>

        <h3 className="text-lg font-semibold text-slate-900 mb-1">{property.name}</h3>
        
        <div className="flex items-center gap-1 text-slate-500 text-sm mb-4">
          <MapPin className="h-4 w-4" />
          <span>{property.address_line1}, {property.city}, {property.state}</span>
        </div>

        <div className="flex items-center justify-between pt-4 border-t">
          <div className="flex items-center gap-2">
            <Home className="h-4 w-4 text-slate-400" />
            <span className="text-sm text-slate-600">{property.unit_count} units</span>
          </div>
          <ChevronRight className="h-5 w-5 text-slate-400" />
        </div>
      </div>
    </Link>
  )
}
