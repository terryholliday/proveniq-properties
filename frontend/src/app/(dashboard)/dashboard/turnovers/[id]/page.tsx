'use client'

import { useEffect, useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { turnoversApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  ArrowLeft, 
  Camera,
  CheckCircle,
  Loader2,
  Sparkles,
  Clock,
  AlertTriangle,
  Upload,
  Check,
  X
} from 'lucide-react'

const PHOTO_TYPES = [
  { key: 'bed', label: 'Bed', description: 'Bed made, linens fresh' },
  { key: 'kitchen', label: 'Kitchen', description: 'Clean, appliances ready' },
  { key: 'bathroom', label: 'Bathroom', description: 'Sanitized, toiletries placed' },
  { key: 'towels', label: 'Towels', description: 'Fresh towels placed' },
  { key: 'keys', label: 'Keys', description: 'Keys/lockbox ready' },
]

interface TurnoverPhoto {
  id: string
  photo_type: string
  object_path: string
  file_hash: string
  notes: string | null
  is_flagged: boolean
  uploaded_at: string
}

interface Turnover {
  id: string
  unit_id: string
  scheduled_date: string
  due_by: string | null
  status: string
  started_at: string | null
  completed_at: string | null
  verified_at: string | null
  cleaner_notes: string | null
  host_notes: string | null
  has_damage: boolean
  needs_restock: boolean
  photos: TurnoverPhoto[]
  photos_complete: boolean
}

export default function TurnoverDetailPage() {
  const params = useParams()
  const router = useRouter()
  const turnoverId = params.id as string
  const { getIdToken } = useAuth()
  
  const [turnover, setTurnover] = useState<Turnover | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedPhotoType, setSelectedPhotoType] = useState<string | null>(null)

  useEffect(() => {
    loadTurnover()
  }, [turnoverId])

  const loadTurnover = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await turnoversApi.get(turnoverId, token)
      setTurnover(data)
    } catch (error) {
      console.error('Failed to load turnover:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePhotoClick = (photoType: string) => {
    const existingPhoto = turnover?.photos.find(p => p.photo_type === photoType)
    if (existingPhoto) return // Already uploaded

    setSelectedPhotoType(photoType)
    fileInputRef.current?.click()
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !selectedPhotoType || !turnover) return

    setUploading(selectedPhotoType)

    try {
      const token = await getIdToken()
      if (!token) throw new Error('Not authenticated')

      // Get presigned URL
      const presign = await turnoversApi.presignPhoto(
        turnoverId,
        {
          photo_type: selectedPhotoType,
          mime_type: file.type || 'image/jpeg',
          file_size_bytes: file.size,
        },
        token
      )

      // Upload to storage
      await fetch(presign.upload_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type || 'image/jpeg',
        },
      })

      // Calculate hash (simplified - in production use crypto API)
      const arrayBuffer = await file.arrayBuffer()
      const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer)
      const hashArray = Array.from(new Uint8Array(hashBuffer))
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')

      // Confirm upload
      await turnoversApi.confirmPhoto(
        turnoverId,
        {
          object_path: presign.object_path,
          photo_type: selectedPhotoType,
          file_hash: hashHex,
          file_size_bytes: file.size,
        },
        token
      )

      // Reload turnover
      loadTurnover()
    } catch (error) {
      console.error('Failed to upload photo:', error)
      alert('Failed to upload photo')
    } finally {
      setUploading(null)
      setSelectedPhotoType(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleComplete = async () => {
    if (!turnover) return
    setActionLoading(true)

    try {
      const token = await getIdToken()
      if (!token) throw new Error('Not authenticated')

      await turnoversApi.complete(turnoverId, token)
      loadTurnover()
    } catch (error: any) {
      alert(error.message || 'Failed to complete turnover')
    } finally {
      setActionLoading(false)
    }
  }

  const handleVerify = async () => {
    if (!turnover) return
    setActionLoading(true)

    try {
      const token = await getIdToken()
      if (!token) throw new Error('Not authenticated')

      await turnoversApi.verify(turnoverId, token)
      loadTurnover()
    } catch (error: any) {
      alert(error.message || 'Failed to verify turnover')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!turnover) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Turnover not found</p>
        <Link href="/dashboard/turnovers">
          <Button variant="outline" className="mt-4">
            Back to Turnovers
          </Button>
        </Link>
      </div>
    )
  }

  const uploadedTypes = new Set(turnover.photos.map(p => p.photo_type))
  const isEditable = turnover.status === 'pending' || turnover.status === 'in_progress'

  return (
    <div className="space-y-6">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFileSelect}
      />

      {/* Header */}
      <div>
        <Link
          href="/dashboard/turnovers"
          className="inline-flex items-center text-sm text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Turnovers
        </Link>
        
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">Turnover</h1>
              <StatusBadge status={turnover.status} />
            </div>
            <p className="text-slate-500 mt-1">
              Scheduled: {new Date(turnover.scheduled_date).toLocaleDateString()}
              {turnover.due_by && ` • Due by ${new Date(turnover.due_by).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {turnover.status === 'in_progress' && turnover.photos_complete && (
              <Button onClick={handleComplete} disabled={actionLoading}>
                {actionLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Complete
              </Button>
            )}
            {turnover.status === 'completed' && (
              <Button onClick={handleVerify} disabled={actionLoading}>
                {actionLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <CheckCircle className="h-4 w-4 mr-2" />
                )}
                Verify
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Status Banner */}
      {turnover.status === 'verified' && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-green-600" />
          <div>
            <p className="font-medium text-green-800">Turnover Verified</p>
            <p className="text-sm text-green-600">
              Verified on {new Date(turnover.verified_at!).toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {turnover.status === 'flagged' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-red-600" />
          <div>
            <p className="font-medium text-red-800">Issue Flagged</p>
            {turnover.host_notes && (
              <p className="text-sm text-red-600">{turnover.host_notes}</p>
            )}
          </div>
        </div>
      )}

      {/* Photo Checklist */}
      <div className="bg-white rounded-xl border">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold">Photo Checklist</h2>
          <p className="text-sm text-slate-500">
            {turnover.photos_complete 
              ? 'All 5 mandatory photos uploaded'
              : `${uploadedTypes.size}/5 photos uploaded`}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 p-6">
          {PHOTO_TYPES.map((type) => {
            const photo = turnover.photos.find(p => p.photo_type === type.key)
            const isUploading = uploading === type.key

            return (
              <div
                key={type.key}
                onClick={() => isEditable && handlePhotoClick(type.key)}
                className={`border rounded-lg p-4 text-center transition-all ${
                  photo 
                    ? 'border-green-300 bg-green-50' 
                    : isEditable
                      ? 'border-dashed border-slate-300 hover:border-primary cursor-pointer'
                      : 'border-slate-200 bg-slate-50'
                }`}
              >
                <div className={`mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-3 ${
                  photo ? 'bg-green-100' : 'bg-slate-100'
                }`}>
                  {isUploading ? (
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  ) : photo ? (
                    <CheckCircle className="h-6 w-6 text-green-600" />
                  ) : (
                    <Camera className="h-6 w-6 text-slate-400" />
                  )}
                </div>
                <p className="font-medium text-sm">{type.label}</p>
                <p className="text-xs text-slate-500 mt-1">{type.description}</p>
                {photo && (
                  <p className="text-xs text-green-600 mt-2">✓ Uploaded</p>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Flags */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="text-lg font-semibold mb-4">Status Flags</h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={turnover.has_damage}
              disabled
              className="w-4 h-4 rounded border-slate-300"
            />
            <span className={turnover.has_damage ? 'text-red-600 font-medium' : 'text-slate-600'}>
              Damage Found
            </span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={turnover.needs_restock}
              disabled
              className="w-4 h-4 rounded border-slate-300"
            />
            <span className={turnover.needs_restock ? 'text-amber-600 font-medium' : 'text-slate-600'}>
              Needs Restock
            </span>
          </label>
        </div>
      </div>

      {/* Notes */}
      {(turnover.cleaner_notes || turnover.host_notes) && (
        <div className="bg-white rounded-xl border p-6">
          <h2 className="text-lg font-semibold mb-4">Notes</h2>
          {turnover.cleaner_notes && (
            <div className="mb-4">
              <p className="text-sm font-medium text-slate-700">Cleaner Notes:</p>
              <p className="text-slate-600">{turnover.cleaner_notes}</p>
            </div>
          )}
          {turnover.host_notes && (
            <div>
              <p className="text-sm font-medium text-slate-700">Host Notes:</p>
              <p className="text-slate-600">{turnover.host_notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
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
