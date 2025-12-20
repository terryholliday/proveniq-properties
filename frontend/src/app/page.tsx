'use client'

import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { Building2, Shield, FileCheck, Wrench } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function HomePage() {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && user) {
      router.push('/dashboard')
    }
  }, [user, loading, router])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Building2 className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold">PROVENIQ Properties</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/login">
              <Button variant="ghost">Sign In</Button>
            </Link>
            <Link href="/register">
              <Button>Get Started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="container mx-auto px-4 py-24 text-center">
        <h1 className="text-5xl font-bold tracking-tight text-slate-900 mb-6">
          Immutable Evidence for
          <span className="text-primary"> Property Management</span>
        </h1>
        <p className="text-xl text-slate-600 max-w-2xl mx-auto mb-10">
          Protect deposits, streamline inspections, and manage maintenance with 
          tamper-proof evidence that holds up in any dispute.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link href="/register">
            <Button size="lg" className="text-lg px-8">
              Start Free Trial
            </Button>
          </Link>
          <Link href="/demo">
            <Button size="lg" variant="outline" className="text-lg px-8">
              Watch Demo
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-16">
        <div className="grid md:grid-cols-3 gap-8">
          <FeatureCard
            icon={<Shield className="h-10 w-10 text-primary" />}
            title="Immutable Inspections"
            description="SHA-256 hashed evidence with timestamps. Once signed, inspections cannot be altered."
          />
          <FeatureCard
            icon={<FileCheck className="h-10 w-10 text-primary" />}
            title="Tenant Invites"
            description="Magic link invites for tenants. Collaborative move-in/move-out inspections."
          />
          <FeatureCard
            icon={<Wrench className="h-10 w-10 text-primary" />}
            title="Smart Maintenance"
            description="AI-powered triage and cost estimates. Track every request from open to close."
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-white mt-16">
        <div className="container mx-auto px-4 py-8 text-center text-slate-600">
          <p>© 2025 PROVENIQ Technologies. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({ 
  icon, 
  title, 
  description 
}: { 
  icon: React.ReactNode
  title: string
  description: string 
}) {
  return (
    <div className="bg-white rounded-xl p-8 shadow-sm border hover:shadow-md transition-shadow">
      <div className="mb-4">{icon}</div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-slate-600">{description}</p>
    </div>
  )
}
