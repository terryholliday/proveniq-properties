'use client'

import { useState } from 'react'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { 
  Building2, 
  Bell, 
  Shield, 
  CreditCard,
  Globe,
  Save,
  Check
} from 'lucide-react'

export default function SettingsPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('organization')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Organization settings
  const [orgName, setOrgName] = useState('My Organization')
  const [orgEmail, setOrgEmail] = useState('')
  const [orgPhone, setOrgPhone] = useState('')
  const [orgAddress, setOrgAddress] = useState('')

  // Notification settings
  const [emailNotifs, setEmailNotifs] = useState(true)
  const [inspectionReminders, setInspectionReminders] = useState(true)
  const [maintenanceAlerts, setMaintenanceAlerts] = useState(true)
  const [turnoverNotifs, setTurnoverNotifs] = useState(true)

  const handleSave = async () => {
    setSaving(true)
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000))
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const tabs = [
    { id: 'organization', label: 'Organization', icon: Building2 },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'integrations', label: 'Integrations', icon: Globe },
    { id: 'billing', label: 'Billing', icon: CreditCard },
    { id: 'security', label: 'Security', icon: Shield },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-slate-600">Manage your organization settings</p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar Tabs */}
        <div className="w-48 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors ${
                  activeTab === tab.id
                    ? 'bg-primary text-white'
                    : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Content */}
        <div className="flex-1 bg-white rounded-lg border p-6">
          {activeTab === 'organization' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-4">Organization Details</h2>
                <div className="grid gap-4 max-w-md">
                  <div>
                    <label className="block text-sm font-medium mb-1">Organization Name</label>
                    <Input
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      placeholder="Your organization name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Contact Email</label>
                    <Input
                      type="email"
                      value={orgEmail}
                      onChange={(e) => setOrgEmail(e.target.value)}
                      placeholder="contact@example.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Phone</label>
                    <Input
                      type="tel"
                      value={orgPhone}
                      onChange={(e) => setOrgPhone(e.target.value)}
                      placeholder="+1 (555) 000-0000"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Address</label>
                    <Input
                      value={orgAddress}
                      onChange={(e) => setOrgAddress(e.target.value)}
                      placeholder="123 Main St, City, ST 12345"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t">
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? (
                    'Saving...'
                  ) : saved ? (
                    <>
                      <Check className="h-4 w-4 mr-2" />
                      Saved
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold">Notification Preferences</h2>
              
              <div className="space-y-4">
                <label className="flex items-center justify-between p-3 bg-slate-50 rounded-lg cursor-pointer">
                  <div>
                    <p className="font-medium">Email Notifications</p>
                    <p className="text-sm text-slate-600">Receive updates via email</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={emailNotifs}
                    onChange={(e) => setEmailNotifs(e.target.checked)}
                    className="h-5 w-5"
                  />
                </label>

                <label className="flex items-center justify-between p-3 bg-slate-50 rounded-lg cursor-pointer">
                  <div>
                    <p className="font-medium">Inspection Reminders</p>
                    <p className="text-sm text-slate-600">Get reminded before scheduled inspections</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={inspectionReminders}
                    onChange={(e) => setInspectionReminders(e.target.checked)}
                    className="h-5 w-5"
                  />
                </label>

                <label className="flex items-center justify-between p-3 bg-slate-50 rounded-lg cursor-pointer">
                  <div>
                    <p className="font-medium">Maintenance Alerts</p>
                    <p className="text-sm text-slate-600">Notifications for new maintenance requests</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={maintenanceAlerts}
                    onChange={(e) => setMaintenanceAlerts(e.target.checked)}
                    className="h-5 w-5"
                  />
                </label>

                <label className="flex items-center justify-between p-3 bg-slate-50 rounded-lg cursor-pointer">
                  <div>
                    <p className="font-medium">Turnover Updates</p>
                    <p className="text-sm text-slate-600">STR turnover status changes</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={turnoverNotifs}
                    onChange={(e) => setTurnoverNotifs(e.target.checked)}
                    className="h-5 w-5"
                  />
                </label>
              </div>

              <div className="pt-4 border-t">
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? 'Saving...' : 'Save Preferences'}
                </Button>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold">Integrations</h2>
              
              <div className="space-y-4">
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <span className="font-bold text-blue-600">CIQ</span>
                      </div>
                      <div>
                        <p className="font-medium">PROVENIQ ClaimsIQ</p>
                        <p className="text-sm text-slate-600">Automated claim processing</p>
                      </div>
                    </div>
                    <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-medium rounded-full">
                      Connected
                    </span>
                  </div>
                </div>

                <div className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 bg-purple-100 rounded-lg flex items-center justify-center">
                        <span className="font-bold text-purple-600">CAP</span>
                      </div>
                      <div>
                        <p className="font-medium">PROVENIQ Capital</p>
                        <p className="text-sm text-slate-600">Payout settlement</p>
                      </div>
                    </div>
                    <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-medium rounded-full">
                      Connected
                    </span>
                  </div>
                </div>

                <div className="p-4 border rounded-lg opacity-60">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 bg-slate-100 rounded-lg flex items-center justify-center">
                        <span className="font-bold text-slate-600">QBO</span>
                      </div>
                      <div>
                        <p className="font-medium">QuickBooks Online</p>
                        <p className="text-sm text-slate-600">Accounting sync</p>
                      </div>
                    </div>
                    <Button variant="outline" size="sm">Connect</Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'billing' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold">Billing & Subscription</h2>
              
              <div className="p-4 bg-slate-50 rounded-lg">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="font-medium">Current Plan</p>
                    <p className="text-2xl font-bold text-primary">Professional</p>
                  </div>
                  <Button variant="outline">Upgrade</Button>
                </div>
                <div className="text-sm text-slate-600">
                  <p>• Unlimited properties</p>
                  <p>• Unlimited inspections</p>
                  <p>• STR turnover support</p>
                  <p>• ClaimsIQ integration</p>
                </div>
              </div>

              <div>
                <h3 className="font-medium mb-2">Payment Method</h3>
                <div className="p-3 border rounded-lg flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CreditCard className="h-5 w-5 text-slate-400" />
                    <span>•••• •••• •••• 4242</span>
                  </div>
                  <Button variant="ghost" size="sm">Update</Button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold">Security Settings</h2>
              
              <div className="space-y-4">
                <div className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Two-Factor Authentication</p>
                      <p className="text-sm text-slate-600">Add an extra layer of security</p>
                    </div>
                    <Button variant="outline" size="sm">Enable</Button>
                  </div>
                </div>

                <div className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Session Management</p>
                      <p className="text-sm text-slate-600">View and manage active sessions</p>
                    </div>
                    <Button variant="outline" size="sm">Manage</Button>
                  </div>
                </div>

                <div className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">API Keys</p>
                      <p className="text-sm text-slate-600">Manage API access tokens</p>
                    </div>
                    <Button variant="outline" size="sm">View Keys</Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
