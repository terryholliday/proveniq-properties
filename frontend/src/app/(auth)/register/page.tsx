'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth'
import { orgApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Building2, Loader2 } from 'lucide-react'

export default function RegisterPage() {
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [orgName, setOrgName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { signUp, getIdToken } = useAuth()
  const router = useRouter()

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await signUp(email, password)
      setStep(2)
    } catch (err: any) {
      setError(err.message || 'Failed to create account')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const token = await getIdToken()
      if (!token) throw new Error('Not authenticated')

      const slug = orgName.toLowerCase().replace(/[^a-z0-9]+/g, '-')
      await orgApi.create({ name: orgName, slug }, token)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Failed to create organization')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-lg border p-8">
          {/* Logo */}
          <div className="flex items-center justify-center gap-2 mb-8">
            <Building2 className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold">PROVENIQ Properties</span>
          </div>

          {step === 1 ? (
            <>
              <h1 className="text-2xl font-bold text-center mb-2">Create your account</h1>
              <p className="text-slate-600 text-center mb-8">
                Start managing properties with immutable evidence
              </p>

              {error && (
                <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6 text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSignUp} className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                    placeholder="you@example.com"
                    required
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                    placeholder="••••••••"
                    minLength={8}
                    required
                  />
                  <p className="text-xs text-slate-500 mt-1">At least 8 characters</p>
                </div>

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating account...
                    </>
                  ) : (
                    'Create Account'
                  )}
                </Button>
              </form>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-center mb-2">Set up your organization</h1>
              <p className="text-slate-600 text-center mb-8">
                This is your property management company or landlord name
              </p>

              {error && (
                <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6 text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleCreateOrg} className="space-y-4">
                <div>
                  <label htmlFor="orgName" className="block text-sm font-medium text-slate-700 mb-1">
                    Organization Name
                  </label>
                  <input
                    id="orgName"
                    type="text"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                    placeholder="Acme Properties LLC"
                    required
                  />
                </div>

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Setting up...
                    </>
                  ) : (
                    'Continue to Dashboard'
                  )}
                </Button>
              </form>
            </>
          )}

          <p className="text-center text-sm text-slate-600 mt-6">
            Already have an account?{' '}
            <Link href="/login" className="text-primary font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
