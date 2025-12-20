'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { propertiesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Loader2, Building2, Home } from 'lucide-react'

export default function NewPropertyPage() {
  const { getIdToken } = useAuth()
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [formData, setFormData] = useState({
    name: '',
    property_type: 'residential',
    address_line1: '',
    city: '',
    state: '',
    zip_code: '',
    total_leasable_sq_ft: '',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const token = await getIdToken()
      if (!token) throw new Error('Not authenticated')

      await propertiesApi.create(
        {
          name: formData.name,
          property_type: formData.property_type,
          address_line1: formData.address_line1,
          city: formData.city,
          state: formData.state,
          zip_code: formData.zip_code,
          total_leasable_sq_ft: formData.total_leasable_sq_ft
            ? parseInt(formData.total_leasable_sq_ft)
            : undefined,
        },
        token
      )

      router.push('/dashboard/properties')
    } catch (err: any) {
      setError(err.message || 'Failed to create property')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/dashboard/properties"
          className="inline-flex items-center text-sm text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Properties
        </Link>
        <h1 className="text-2xl font-bold text-slate-900">Add Property</h1>
        <p className="text-slate-600">Enter the details for your new property</p>
      </div>

      {/* Form */}
      <div className="bg-white rounded-xl border p-6">
        {error && (
          <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Property Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-3">
              Property Type
            </label>
            <div className="grid grid-cols-3 gap-3">
              <PropertyTypeOption
                type="residential"
                label="Residential"
                icon={<Home className="h-5 w-5" />}
                selected={formData.property_type === 'residential'}
                onSelect={() => setFormData({ ...formData, property_type: 'residential' })}
              />
              <PropertyTypeOption
                type="commercial"
                label="Commercial"
                icon={<Building2 className="h-5 w-5" />}
                selected={formData.property_type === 'commercial'}
                onSelect={() => setFormData({ ...formData, property_type: 'commercial' })}
              />
              <PropertyTypeOption
                type="mixed"
                label="Mixed Use"
                icon={<Building2 className="h-5 w-5" />}
                selected={formData.property_type === 'mixed'}
                onSelect={() => setFormData({ ...formData, property_type: 'mixed' })}
              />
            </div>
          </div>

          {/* Property Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1">
              Property Name
            </label>
            <input
              id="name"
              name="name"
              type="text"
              value={formData.name}
              onChange={handleChange}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
              placeholder="e.g., Sunrise Apartments"
              required
            />
          </div>

          {/* Address */}
          <div>
            <label htmlFor="address_line1" className="block text-sm font-medium text-slate-700 mb-1">
              Street Address
            </label>
            <input
              id="address_line1"
              name="address_line1"
              type="text"
              value={formData.address_line1}
              onChange={handleChange}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
              placeholder="123 Main Street"
              required
            />
          </div>

          {/* City, State, Zip */}
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-1">
              <label htmlFor="city" className="block text-sm font-medium text-slate-700 mb-1">
                City
              </label>
              <input
                id="city"
                name="city"
                type="text"
                value={formData.city}
                onChange={handleChange}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                required
              />
            </div>
            <div>
              <label htmlFor="state" className="block text-sm font-medium text-slate-700 mb-1">
                State
              </label>
              <input
                id="state"
                name="state"
                type="text"
                value={formData.state}
                onChange={handleChange}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                maxLength={2}
                placeholder="TX"
                required
              />
            </div>
            <div>
              <label htmlFor="zip_code" className="block text-sm font-medium text-slate-700 mb-1">
                ZIP Code
              </label>
              <input
                id="zip_code"
                name="zip_code"
                type="text"
                value={formData.zip_code}
                onChange={handleChange}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                required
              />
            </div>
          </div>

          {/* Square Footage (Commercial) */}
          {formData.property_type !== 'residential' && (
            <div>
              <label htmlFor="total_leasable_sq_ft" className="block text-sm font-medium text-slate-700 mb-1">
                Total Leasable Sq Ft
              </label>
              <input
                id="total_leasable_sq_ft"
                name="total_leasable_sq_ft"
                type="number"
                value={formData.total_leasable_sq_ft}
                onChange={handleChange}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                placeholder="10000"
              />
              <p className="text-xs text-slate-500 mt-1">Required for commercial properties</p>
            </div>
          )}

          {/* Submit */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t">
            <Link href="/dashboard/properties">
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </Link>
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Property'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function PropertyTypeOption({
  type,
  label,
  icon,
  selected,
  onSelect,
}: {
  type: string
  label: string
  icon: React.ReactNode
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`p-4 border rounded-lg text-center transition-all ${
        selected
          ? 'border-primary bg-primary/5 text-primary'
          : 'border-slate-200 hover:border-slate-300'
      }`}
    >
      <div className={`mx-auto mb-2 ${selected ? 'text-primary' : 'text-slate-400'}`}>
        {icon}
      </div>
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}
