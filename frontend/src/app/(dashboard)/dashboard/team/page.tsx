'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { 
  Users, 
  Plus, 
  Search, 
  Mail,
  Shield,
  MoreVertical,
  UserPlus,
  Trash2,
  Crown
} from 'lucide-react'

interface TeamMember {
  id: string
  email: string
  name: string | null
  role: 'ORG_OWNER' | 'ORG_ADMIN' | 'ORG_MEMBER' | 'ORG_VIEWER' | 'ORG_CLEANER'
  joined_at: string
  last_active: string | null
}

const roleLabels: Record<string, string> = {
  ORG_OWNER: 'Owner',
  ORG_ADMIN: 'Admin',
  ORG_MEMBER: 'Member',
  ORG_VIEWER: 'Viewer',
  ORG_CLEANER: 'Cleaner',
}

const roleColors: Record<string, string> = {
  ORG_OWNER: 'bg-purple-100 text-purple-800',
  ORG_ADMIN: 'bg-blue-100 text-blue-800',
  ORG_MEMBER: 'bg-green-100 text-green-800',
  ORG_VIEWER: 'bg-slate-100 text-slate-800',
  ORG_CLEANER: 'bg-amber-100 text-amber-800',
}

export default function TeamPage() {
  const { getIdToken } = useAuth()
  const [members, setMembers] = useState<TeamMember[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [showInviteModal, setShowInviteModal] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('ORG_MEMBER')
  const [inviting, setInviting] = useState(false)

  useEffect(() => {
    fetchTeamMembers()
  }, [])

  const fetchTeamMembers = async () => {
    try {
      const token = await getIdToken()
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/organizations/members`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      if (response.ok) {
        const data = await response.json()
        setMembers(data.members || [])
      }
    } catch (error) {
      console.error('Failed to fetch team members:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleInvite = async () => {
    if (!inviteEmail) return
    
    setInviting(true)
    try {
      const token = await getIdToken()
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/organizations/invite`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: inviteEmail,
          role: inviteRole,
        }),
      })
      
      if (response.ok) {
        setShowInviteModal(false)
        setInviteEmail('')
        fetchTeamMembers()
      }
    } catch (error) {
      console.error('Failed to send invite:', error)
    } finally {
      setInviting(false)
    }
  }

  const filteredMembers = members.filter(member =>
    member.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    member.name?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

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
          <h1 className="text-2xl font-bold">Team</h1>
          <p className="text-slate-600">Manage your organization members</p>
        </div>
        <Button onClick={() => setShowInviteModal(true)}>
          <UserPlus className="h-4 w-4 mr-2" />
          Invite Member
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Users className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Total Members</p>
              <p className="text-2xl font-bold">{members.length}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Shield className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Admins</p>
              <p className="text-2xl font-bold">
                {members.filter(m => m.role === 'ORG_ADMIN' || m.role === 'ORG_OWNER').length}
              </p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <Users className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Members</p>
              <p className="text-2xl font-bold">
                {members.filter(m => m.role === 'ORG_MEMBER').length}
              </p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 rounded-lg">
              <Users className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-sm text-slate-600">Cleaners</p>
              <p className="text-2xl font-bold">
                {members.filter(m => m.role === 'ORG_CLEANER').length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          placeholder="Search by name or email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Team Members List */}
      {filteredMembers.length === 0 ? (
        <div className="bg-white rounded-lg border p-8 text-center">
          <Users className="h-12 w-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No team members found</h3>
          <p className="text-slate-600 mb-4">
            {searchQuery 
              ? 'Try adjusting your search'
              : 'Get started by inviting your first team member'}
          </p>
          {!searchQuery && (
            <Button onClick={() => setShowInviteModal(true)}>
              <UserPlus className="h-4 w-4 mr-2" />
              Invite Member
            </Button>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-600">Member</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-600">Role</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-600">Joined</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-slate-600">Last Active</th>
                <th className="px-4 py-3 text-right text-sm font-medium text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredMembers.map((member) => (
                <tr key={member.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-slate-200 flex items-center justify-center">
                        <span className="text-sm font-medium text-slate-600">
                          {(member.name || member.email).charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium flex items-center gap-1">
                          {member.name || 'Unnamed'}
                          {member.role === 'ORG_OWNER' && (
                            <Crown className="h-4 w-4 text-amber-500" />
                          )}
                        </p>
                        <p className="text-sm text-slate-600">{member.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${roleColors[member.role]}`}>
                      {roleLabels[member.role]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {formatDate(member.joined_at)}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {member.last_active ? formatDate(member.last_active) : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="ghost" size="sm">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">Invite Team Member</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Email</label>
                <Input
                  type="email"
                  placeholder="colleague@example.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Role</label>
                <select
                  className="w-full px-3 py-2 border rounded-lg"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                >
                  <option value="ORG_ADMIN">Admin</option>
                  <option value="ORG_MEMBER">Member</option>
                  <option value="ORG_VIEWER">Viewer</option>
                  <option value="ORG_CLEANER">Cleaner (STR)</option>
                </select>
              </div>
            </div>
            
            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={() => setShowInviteModal(false)}>
                Cancel
              </Button>
              <Button onClick={handleInvite} disabled={inviting || !inviteEmail}>
                {inviting ? 'Sending...' : 'Send Invite'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
