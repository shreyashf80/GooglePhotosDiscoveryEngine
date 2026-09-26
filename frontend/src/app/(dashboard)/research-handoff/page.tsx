import { fetchApi } from '@/lib/api'
import HandoffClient from './client'
import { Suspense } from 'react'
import { LoadingState } from '@/components/shared/components'

export const revalidate = 300;

async function HandoffData() {
  const data = await fetchApi<any>('/handoff')
  return <HandoffClient handoff={data} />
}

export default function ResearchHandoffPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Research Handoff</h1>
        <p className="text-muted-foreground mt-2">Decisions and AI-drafted assets for user research validation (Part 2).</p>
      </div>
      <Suspense fallback={<LoadingState />}>
        <HandoffData />
      </Suspense>
    </div>
  )
}
