'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { inspectionsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { 
  ArrowLeft, 
  Download, 
  FileCheck, 
  Loader2,
  Shield,
  DollarSign,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'

interface DiffItem {
  room_name: string
  item_name: string
  move_in_condition: number | null
  move_out_condition: number | null
  condition_change: number
  is_new_damage: boolean
  damage_description: string | null
  mason_estimated_repair_cents: number | null
}

interface DiffResponse {
  lease_id: string
  move_in_inspection_id: string
  move_out_inspection_id: string
  items: DiffItem[]
  total_items: number
  damaged_items: number
  total_estimated_repair_cents: number
}

export default function LeaseDetailPage() {
  const params = useParams()
  const leaseId = params.id as string
  const { getIdToken } = useAuth()
  
  const [diff, setDiff] = useState<DiffResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadDiff()
  }, [leaseId])

  const loadDiff = async () => {
    try {
      const token = await getIdToken()
      if (!token) return

      const data = await inspectionsApi.getDiff(leaseId, token) as DiffResponse
      setDiff(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load inspection diff')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadClaimPacket = async () => {
    setDownloading(true)
    try {
      const token = await getIdToken()
      if (!token) throw new Error('Not authenticated')

      await inspectionsApi.downloadClaimPacket(leaseId, token, true)
    } catch (err: any) {
      alert(err.message || 'Failed to download claim packet')
    } finally {
      setDownloading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto">
        <Link
          href="/dashboard/properties"
          className="inline-flex items-center text-sm text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Link>
        
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
          <AlertTriangle className="h-12 w-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-amber-800 mb-2">Cannot Generate Claim Packet</h2>
          <p className="text-amber-600">{error}</p>
          <p className="text-sm text-amber-500 mt-4">
            Both move-in and move-out inspections must be signed to generate a claim packet.
          </p>
        </div>
      </div>
    )
  }

  if (!diff) {
    return null
  }

  const damagedItems = diff.items.filter(i => i.condition_change < 0 || i.is_new_damage)
  const totalDamage = diff.total_estimated_repair_cents

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
            <h1 className="text-2xl font-bold text-slate-900">Inspection Comparison</h1>
            <p className="text-slate-500">Move-in vs Move-out damage assessment</p>
          </div>
          
          <Button 
            onClick={handleDownloadClaimPacket} 
            disabled={downloading}
            className="gap-2"
          >
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Download Claim Packet
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
              <FileCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">{diff.total_items}</p>
              <p className="text-sm text-slate-500">Items Inspected</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${damagedItems.length > 0 ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'}`}>
              {damagedItems.length > 0 ? (
                <AlertTriangle className="h-5 w-5" />
              ) : (
                <CheckCircle className="h-5 w-5" />
              )}
            </div>
            <div>
              <p className="text-2xl font-bold">{damagedItems.length}</p>
              <p className="text-sm text-slate-500">Items Damaged</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 rounded-lg text-amber-600">
              <DollarSign className="h-5 w-5" />
            </div>
            <div>
              <p className="text-2xl font-bold">${(totalDamage / 100).toFixed(2)}</p>
              <p className="text-sm text-slate-500">Estimated Repairs</p>
            </div>
          </div>
        </div>
      </div>

      {/* Claim Packet Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-start gap-4">
          <Shield className="h-6 w-6 text-blue-600 mt-1" />
          <div>
            <h3 className="font-semibold text-blue-800">Claim Packet Ready</h3>
            <p className="text-blue-600 mt-1">
              Download a complete claim packet with all evidence, inspection hashes, and cost estimates.
              This ZIP file can be submitted directly to Airbnb Resolution Center, VRBO, or your insurance provider.
            </p>
            <div className="flex items-center gap-2 mt-3">
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">SHA-256 Verified</span>
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">Tamper-Proof</span>
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">Timestamped</span>
            </div>
          </div>
        </div>
      </div>

      {/* Damage List */}
      {damagedItems.length > 0 && (
        <div className="bg-white rounded-xl border">
          <div className="p-6 border-b">
            <h2 className="text-lg font-semibold">Damage Details</h2>
          </div>
          <div className="divide-y">
            {damagedItems.map((item, index) => (
              <div key={index} className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{item.room_name} / {item.item_name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-sm text-slate-500">
                        Condition: {item.move_in_condition} → {item.move_out_condition}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        item.condition_change <= -3 ? 'bg-red-100 text-red-700' :
                        item.condition_change <= -1 ? 'bg-amber-100 text-amber-700' :
                        'bg-slate-100 text-slate-600'
                      }`}>
                        {item.condition_change > 0 ? '+' : ''}{item.condition_change}
                      </span>
                    </div>
                    {item.damage_description && (
                      <p className="text-sm text-slate-600 mt-2">{item.damage_description}</p>
                    )}
                  </div>
                  {item.mason_estimated_repair_cents && item.mason_estimated_repair_cents > 0 && (
                    <div className="text-right">
                      <p className="font-medium text-amber-600">
                        ${(item.mason_estimated_repair_cents / 100).toFixed(2)}
                      </p>
                      <p className="text-xs text-slate-500">Est. repair</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Damage */}
      {damagedItems.length === 0 && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-green-800">No Damage Detected</h3>
          <p className="text-green-600">
            The property was returned in the same or better condition.
          </p>
        </div>
      )}
    </div>
  )
}
