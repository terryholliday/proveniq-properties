'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { inspectionsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  ArrowLeft, 
  Plus, 
  FileCheck, 
  Camera,
  Check,
  Loader2,
  Shield,
  AlertTriangle
} from 'lucide-react'

interface InspectionItem {
  id: string
  room_key: string
  item_key: string
  condition: string
  notes?: string
}

interface Inspection {
  id: string
  lease_id: string
  inspection_type: string
  status: string
  inspection_date: string
  content_hash?: string
  items: InspectionItem[]
}

const ROOM_TEMPLATES = [
  { key: 'living_room', label: 'Living Room', items: ['Flooring', 'Walls', 'Ceiling', 'Windows', 'Doors'] },
  { key: 'kitchen', label: 'Kitchen', items: ['Sink', 'Faucet', 'Countertops', 'Cabinets', 'Appliances', 'Flooring'] },
  { key: 'bathroom', label: 'Bathroom', items: ['Toilet', 'Sink', 'Shower/Tub', 'Mirror', 'Flooring', 'Ventilation'] },
  { key: 'bedroom', label: 'Bedroom', items: ['Flooring', 'Walls', 'Closet', 'Windows', 'Doors'] },
  { key: 'exterior', label: 'Exterior', items: ['Entry Door', 'Patio/Balcony', 'Landscaping'] },
]

export default function InspectionDetailPage() {
  const params = useParams()
  const router = useRouter()
  const inspectionId = params.id as string
  const { getIdToken } = useAuth()
  
  const [inspection, setInspection] = useState<Inspection | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [activeRoom, setActiveRoom] = useState(ROOM_TEMPLATES[0].key)
  const [items, setItems] = useState<Map<string, { condition: string; notes: string }>>(new Map())

  useEffect(() => {
    loadInspection()
  }, [inspectionId])

  const loadInspection = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await inspectionsApi.get(inspectionId, token) as Inspection
      setInspection(data)
      
      // Load existing items into state
      const itemsMap = new Map<string, { condition: string; notes: string }>()
      data.items?.forEach(item => {
        const key = `${item.room_key}:${item.item_key}`
        itemsMap.set(key, { condition: item.condition, notes: item.notes || '' })
      })
      setItems(itemsMap)
    } catch (error) {
      console.error('Failed to load inspection:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleItemChange = async (roomKey: string, itemKey: string, condition: string, notes: string) => {
    const key = `${roomKey}:${itemKey}`
    setItems(prev => new Map(prev).set(key, { condition, notes }))

    try {
      const token = await getIdToken()
      if (!token) return

      await inspectionsApi.upsertItem(
        inspectionId,
        {
          room_name: roomKey,
          item_name: itemKey,
          condition_rating: condition === 'good' ? 5 : condition === 'fair' ? 3 : 1,
          is_damaged: condition === 'damaged',
          damage_description: notes,
        },
        token
      )
    } catch (error) {
      console.error('Failed to save item:', error)
    }
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const token = await getIdToken()
      if (!token) return

      await inspectionsApi.submit(inspectionId, token)
      loadInspection()
    } catch (error) {
      console.error('Failed to submit inspection:', error)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSign = async () => {
    setSubmitting(true)
    try {
      const token = await getIdToken()
      if (!token) return

      await inspectionsApi.sign(inspectionId, 'landlord', token)
      loadInspection()
    } catch (error) {
      console.error('Failed to sign inspection:', error)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!inspection) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Inspection not found</p>
        <Link href="/dashboard/inspections">
          <Button variant="outline" className="mt-4">
            Back to Inspections
          </Button>
        </Link>
      </div>
    )
  }

  const isEditable = inspection.status === 'draft' || inspection.status === 'in_progress'
  const isSubmitted = inspection.status === 'submitted'
  const isSigned = inspection.status === 'signed'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/dashboard/inspections"
          className="inline-flex items-center text-sm text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Inspections
        </Link>
        
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">
                {formatInspectionType(inspection.inspection_type)}
              </h1>
              <StatusBadge status={inspection.status} />
            </div>
            <p className="text-slate-500 mt-1">
              {new Date(inspection.inspection_date).toLocaleDateString()}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {isEditable && (
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Submit
              </Button>
            )}
            {isSubmitted && (
              <Button onClick={handleSign} disabled={submitting}>
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Shield className="h-4 w-4 mr-2" />
                )}
                Sign
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Signed Notice */}
      {isSigned && inspection.content_hash && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
          <Shield className="h-5 w-5 text-green-600 mt-0.5" />
          <div>
            <p className="font-medium text-green-800">Inspection Signed & Locked</p>
            <p className="text-sm text-green-600 mt-1">
              This inspection is immutable. Content hash:{' '}
              <code className="bg-green-100 px-1 rounded">{inspection.content_hash}</code>
            </p>
          </div>
        </div>
      )}

      {/* Room Tabs */}
      <div className="bg-white rounded-xl border">
        <div className="flex border-b overflow-x-auto">
          {ROOM_TEMPLATES.map((room) => (
            <button
              key={room.key}
              onClick={() => setActiveRoom(room.key)}
              className={`px-6 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                activeRoom === room.key
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {room.label}
            </button>
          ))}
        </div>

        {/* Room Items */}
        <div className="p-6">
          {ROOM_TEMPLATES.filter((r) => r.key === activeRoom).map((room) => (
            <div key={room.key} className="space-y-4">
              {room.items.map((item) => {
                const key = `${room.key}:${item.toLowerCase().replace(/\s+/g, '_')}`
                const itemData = items.get(key) || { condition: 'good', notes: '' }
                
                return (
                  <div key={item} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-medium">{item}</h4>
                        
                        {/* Condition Buttons */}
                        <div className="flex items-center gap-2 mt-3">
                          {['good', 'fair', 'damaged'].map((condition) => (
                            <button
                              key={condition}
                              onClick={() => handleItemChange(
                                room.key,
                                item.toLowerCase().replace(/\s+/g, '_'),
                                condition,
                                itemData.notes
                              )}
                              disabled={!isEditable}
                              className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                                itemData.condition === condition
                                  ? getConditionColor(condition, true)
                                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                              } ${!isEditable ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                              {condition}
                            </button>
                          ))}
                        </div>

                        {/* Notes */}
                        {(itemData.condition === 'damaged' || itemData.notes) && (
                          <textarea
                            value={itemData.notes}
                            onChange={(e) => handleItemChange(
                              room.key,
                              item.toLowerCase().replace(/\s+/g, '_'),
                              itemData.condition,
                              e.target.value
                            )}
                            disabled={!isEditable}
                            placeholder="Describe the damage..."
                            className="mt-3 w-full px-3 py-2 border rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary focus:border-primary outline-none disabled:bg-slate-50"
                            rows={2}
                          />
                        )}
                      </div>

                      {/* Photo Button */}
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!isEditable}
                        className="ml-4"
                      >
                        <Camera className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function formatInspectionType(type: string): string {
  const types: Record<string, string> = {
    move_in: 'Move-In Inspection',
    move_out: 'Move-Out Inspection',
    periodic: 'Periodic Inspection',
    turnover: 'Turnover Inspection',
  }
  return types[type] || type.replace('_', ' ')
}

function getConditionColor(condition: string, selected: boolean): string {
  if (!selected) return 'bg-slate-100 text-slate-500'
  
  const colors: Record<string, string> = {
    good: 'bg-green-100 text-green-700',
    fair: 'bg-amber-100 text-amber-700',
    damaged: 'bg-red-100 text-red-700',
  }
  return colors[condition] || 'bg-slate-100 text-slate-500'
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
