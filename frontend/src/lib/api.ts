const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/v1'

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  token?: string
}

class ApiError extends Error {
  status: number
  details?: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

async function apiRequest<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, token } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(
      error.detail || 'API request failed',
      response.status,
      error
    )
  }

  if (response.status === 204) {
    return {} as T
  }

  return response.json()
}

// Auth API
export const authApi = {
  requestMagicLink: (email: string, leaseId: string, token: string) =>
    apiRequest<{ message: string; lease_id: string }>('/auth/magic-link/request', {
      method: 'POST',
      body: { email, lease_id: leaseId },
      token,
    }),

  verifyMagicLink: (verifyToken: string) =>
    apiRequest<{ firebase_custom_token: string }>('/auth/magic-link/verify', {
      method: 'POST',
      body: { token: verifyToken },
    }),

  getCurrentUser: (token: string) =>
    apiRequest<{
      uid: string
      email: string | null
      db_user_id: string | null
      org_id: string | null
      org_role: string | null
    }>('/auth/me', { token }),
}

// Organizations API
export const orgApi = {
  create: (data: { name: string; slug: string }, token: string) =>
    apiRequest<{ id: string; name: string; slug: string }>('/orgs', {
      method: 'POST',
      body: data,
      token,
    }),

  getMyOrg: (token: string) =>
    apiRequest<{
      id: string
      name: string
      slug: string
      current_user_role: string
    }>('/orgs/me', { token }),
}

// Properties API
export const propertiesApi = {
  list: (token: string) =>
    apiRequest<Array<{
      id: string
      name: string
      property_type: string
      address_line1: string
      city: string
      state: string
      unit_count: number
    }>>('/properties', { token }),

  create: (data: {
    name: string
    property_type: string
    address_line1: string
    city: string
    state: string
    zip_code: string
    total_leasable_sq_ft?: number
  }, token: string) =>
    apiRequest('/properties', { method: 'POST', body: data, token }),

  get: (id: string, token: string) =>
    apiRequest<{ id: string; name: string }>(`/properties/${id}`, { token }),

  listUnits: (propertyId: string, token: string) =>
    apiRequest<Array<{
      id: string
      unit_number: string
      status: string
      sq_ft?: number
    }>>(`/properties/${propertyId}/units`, { token }),

  createUnit: (propertyId: string, data: {
    unit_number: string
    sq_ft?: number
  }, token: string) =>
    apiRequest(`/properties/${propertyId}/units`, { method: 'POST', body: data, token }),
}

// Leases API
export const leasesApi = {
  list: (token: string, unitId?: string) =>
    apiRequest<Array<{
      id: string
      unit_id: string
      lease_type: string
      status: string
      tenant_email: string
      rent_amount_cents: number
    }>>(`/leases${unitId ? `?unit_id=${unitId}` : ''}`, { token }),

  create: (data: {
    unit_id: string
    lease_type: string
    start_date: string
    end_date: string
    rent_amount_cents: number
    deposit_amount_cents: number
    tenant_email: string
    tenant_name?: string
    pro_rata_share_bps?: number
  }, token: string) =>
    apiRequest('/leases', { method: 'POST', body: data, token }),

  sendInvite: (leaseId: string, token: string) =>
    apiRequest<{ lease_id: string; tenant_email: string }>(`/leases/${leaseId}/invite`, {
      method: 'POST',
      body: {},
      token,
    }),
}

// Inspections API
export const inspectionsApi = {
  list: (token: string, leaseId?: string) =>
    apiRequest<Array<{
      id: string
      lease_id: string
      inspection_type: string
      status: string
      inspection_date: string
      content_hash?: string
    }>>(`/inspections${leaseId ? `?lease_id=${leaseId}` : ''}`, { token }),

  create: (data: {
    lease_id: string
    inspection_type: string
    inspection_date: string
  }, token: string) =>
    apiRequest('/inspections', { method: 'POST', body: data, token }),

  get: (id: string, token: string) =>
    apiRequest(`/inspections/${id}`, { token }),

  upsertItem: (inspectionId: string, data: {
    room_name: string
    item_name: string
    condition_rating?: number
    is_damaged?: boolean
    damage_description?: string
  }, token: string) =>
    apiRequest(`/inspections/${inspectionId}/items`, { method: 'POST', body: data, token }),

  presignEvidence: (inspectionId: string, data: {
    item_id: string
    file_name: string
    mime_type: string
    file_size_bytes: number
  }, token: string) =>
    apiRequest<{
      upload_url: string
      object_path: string
      expires_at: string
    }>(`/inspections/${inspectionId}/evidence/presign`, { method: 'POST', body: data, token }),

  confirmEvidence: (inspectionId: string, data: {
    item_id: string
    object_path: string
    file_hash: string
    file_size_bytes: number
    mime_type: string
  }, token: string) =>
    apiRequest(`/inspections/${inspectionId}/evidence/confirm`, { method: 'POST', body: data, token }),

  submit: (inspectionId: string, token: string) =>
    apiRequest<{ inspection_id: string; content_hash: string }>(`/inspections/${inspectionId}/submit`, {
      method: 'POST',
      token,
    }),

  sign: (inspectionId: string, signatureType: 'tenant' | 'landlord', token: string) =>
    apiRequest(`/inspections/${inspectionId}/sign`, {
      method: 'POST',
      body: { signature_type: signatureType },
      token,
    }),

  getDiff: (leaseId: string, token: string) =>
    apiRequest(`/inspections/leases/${leaseId}/inspection-diff`, { token }),

  getMasonEstimate: (leaseId: string, token: string) =>
    apiRequest(`/inspections/leases/${leaseId}/inspection-diff/estimate`, { token }),

  downloadClaimPacket: async (leaseId: string, token: string, includeEvidence: boolean = true) => {
    const response = await fetch(
      `${API_BASE_URL}/inspections/leases/${leaseId}/claim-packet?include_evidence=${includeEvidence}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    )
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new ApiError(error.detail || 'Failed to download claim packet', response.status, error)
    }
    
    // Get filename from Content-Disposition header
    const disposition = response.headers.get('Content-Disposition')
    const filenameMatch = disposition?.match(/filename="(.+)"/)
    const filename = filenameMatch ? filenameMatch[1] : `claim_packet_${leaseId}.zip`
    
    // Download blob
    const blob = await response.blob()
    
    // Trigger download
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    return { filename }
  },
}

// Turnovers API
export const turnoversApi = {
  list: (token: string, params?: { unitId?: string; status?: string; assignedToMe?: boolean }) => {
    const searchParams = new URLSearchParams()
    if (params?.unitId) searchParams.set('unit_id', params.unitId)
    if (params?.status) searchParams.set('status_filter', params.status)
    if (params?.assignedToMe) searchParams.set('assigned_to_me', 'true')
    const query = searchParams.toString()
    return apiRequest<any[]>(`/turnovers${query ? `?${query}` : ''}`, { token })
  },

  get: (id: string, token: string) =>
    apiRequest<any>(`/turnovers/${id}`, { token }),

  create: (data: {
    unit_id: string
    scheduled_date: string
    due_by?: string
    checkout_booking_id?: string
    checkin_booking_id?: string
    assigned_cleaner_id?: string
  }, token: string) =>
    apiRequest(`/turnovers`, { method: 'POST', body: data, token }),

  update: (id: string, data: any, token: string) =>
    apiRequest(`/turnovers/${id}`, { method: 'PATCH', body: data, token }),

  start: (id: string, token: string) =>
    apiRequest(`/turnovers/${id}/start`, { method: 'POST', token }),

  complete: (id: string, token: string) =>
    apiRequest(`/turnovers/${id}/complete`, { method: 'POST', token }),

  verify: (id: string, token: string) =>
    apiRequest(`/turnovers/${id}/verify`, { method: 'POST', token }),

  flag: (id: string, hostNotes: string, token: string) =>
    apiRequest(`/turnovers/${id}/flag?host_notes=${encodeURIComponent(hostNotes)}`, { method: 'POST', token }),

  presignPhoto: (id: string, data: { photo_type: string; mime_type: string; file_size_bytes: number }, token: string) =>
    apiRequest<{ upload_url: string; object_path: string; photo_type: string }>(
      `/turnovers/${id}/photos/presign`,
      { method: 'POST', body: data, token }
    ),

  confirmPhoto: (id: string, data: {
    object_path: string
    photo_type: string
    file_hash: string
    file_size_bytes: number
    notes?: string
  }, token: string) =>
    apiRequest(`/turnovers/${id}/photos/confirm`, { method: 'POST', body: data, token }),

  addInventory: (id: string, data: {
    item_name: string
    location: string
    expected_quantity: number
    actual_quantity: number
    notes?: string
  }, token: string) =>
    apiRequest(`/turnovers/${id}/inventory`, { method: 'POST', body: data, token }),

  getMyTurnovers: (token: string) =>
    apiRequest<any[]>(`/turnovers/cleaners/my-turnovers`, { token }),
}

// Vendors API
export const vendorsApi = {
  list: (token: string) =>
    apiRequest<Array<{
      id: string
      name: string
      specialty: string
      is_preferred: boolean
    }>>('/vendors', { token }),

  create: (data: {
    name: string
    specialty: string
    email?: string
    phone?: string
  }, token: string) =>
    apiRequest('/vendors', { method: 'POST', body: data, token }),
}

// Maintenance API
export const maintenanceApi = {
  list: (token: string, unitId?: string) =>
    apiRequest<Array<{
      id: string
      unit_id: string
      title: string
      status: string
      priority: number
    }>>(`/maintenance${unitId ? `?unit_id=${unitId}` : ''}`, { token }),

  create: (data: {
    unit_id: string
    title: string
    description: string
    priority?: number
  }, token: string) =>
    apiRequest('/maintenance', { method: 'POST', body: data, token }),

  assign: (ticketId: string, data: {
    assigned_vendor_id?: string
    assigned_org_member_user_id?: string
  }, token: string) =>
    apiRequest(`/maintenance/${ticketId}/assign`, { method: 'PATCH', body: data, token }),

  triage: (ticketId: string, token: string) =>
    apiRequest<{
      suggested_category: string
      suggested_priority: number
      estimated_cost_cents?: number
      reasoning: string
    }>(`/maintenance/${ticketId}/triage`, { method: 'POST', body: {}, token }),
}

// Dashboard API
export const dashboardApi = {
  getStats: (token: string) =>
    apiRequest<{
      properties: { total: number; residential: number; commercial: number; mixed_use: number }
      units: { total: number; occupied: number; vacant: number; occupancy_rate: number }
      leases: { total: number; active: number; pending: number; draft: number; expiring_soon: number }
      revenue: { monthly_rent_roll_cents: number; deposits_held_cents: number }
      inspections: { pending: number; completed_this_month: number }
      maintenance: { open: number; in_progress: number; completed_this_month: number }
    }>('/dashboard/stats', { token }),

  getExpiringLeases: (token: string, days: number = 30) =>
    apiRequest<{
      leases: Array<{
        id: string
        tenant_name: string
        tenant_email: string
        end_date: string
        days_until_expiry: number
        rent_amount_cents: number
        unit: { id: string; unit_number: string }
        property: { id: string; name: string; address: string }
      }>
      total: number
      days_window: number
    }>(`/dashboard/leases/expiring?days=${days}`, { token }),

  getRecentActivity: (token: string, limit: number = 20) =>
    apiRequest<{
      activities: Array<{
        type: string
        action: string
        timestamp: string
        details: Record<string, unknown>
      }>
      total: number
    }>(`/dashboard/activity/recent?limit=${limit}`, { token }),

  getOccupancyByProperty: (token: string) =>
    apiRequest<{
      properties: Array<{
        id: string
        name: string
        property_type: string
        total_units: number
        occupied_units: number
        vacancy_rate: number
      }>
      total: number
    }>('/dashboard/occupancy/by-property', { token }),
}

// Reports API
export const reportsApi = {
  getRentRoll: (token: string, propertyId?: string) =>
    apiRequest<{
      generated_at: string
      total_properties: number
      total_units: number
      occupied_units: number
      vacancy_rate: number
      total_monthly_rent_cents: number
      total_annual_rent_cents: number
      properties: Array<{
        property_id: string
        name: string
        total_units: number
        occupied_units: number
        monthly_rent_cents: number
        units: Array<{
          unit_id: string
          unit_number: string
          status: string
          lease?: {
            tenant_name: string
            rent_amount_cents: number
            end_date: string
          }
        }>
      }>
    }>(`/reports/rent-roll${propertyId ? `?property_id=${propertyId}` : ''}`, { token }),

  getLeaseExpiration: (token: string, monthsAhead: number = 12) =>
    apiRequest<{
      total_expiring_leases: number
      total_rent_at_risk_cents: number
      by_month: Array<{
        month: string
        month_label: string
        lease_count: number
        rent_at_risk_cents: number
        leases: Array<{
          lease_id: string
          tenant_name: string
          end_date: string
          rent_amount_cents: number
          property_name: string
        }>
      }>
    }>(`/reports/lease-expiration?months_ahead=${monthsAhead}`, { token }),

  getMaintenanceSummary: (token: string, period: string = 'month') =>
    apiRequest<{
      total_tickets: number
      by_status: Record<string, number>
      by_priority: Record<string, number>
      total_cost_cents: number
      completion_rate: number
    }>(`/reports/maintenance-summary?period=${period}`, { token }),

  getCamReconciliation: (token: string, propertyId: string, year?: number) =>
    apiRequest<{
      property: { id: string; name: string; total_leasable_sq_ft: number }
      total_nnn_tenants: number
      total_annual_cam_budget_cents: number
      tenants: Array<{
        unit_number: string
        tenant_name: string
        pro_rata_share_pct: number
        annual_cam_budget_cents: number
      }>
    }>(`/reports/commercial/cam-reconciliation?property_id=${propertyId}${year ? `&year=${year}` : ''}`, { token }),
}

export { ApiError }
