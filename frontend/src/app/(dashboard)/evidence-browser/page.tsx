import { fetchApi } from '@/lib/api'
import EvidenceClient from './client'
import { Suspense } from 'react'
import { LoadingState } from '@/components/shared/components'

export const revalidate = 300;

async function EvidenceData({ searchParams }: { searchParams: Record<string, string> }) {
  const params = new URLSearchParams(searchParams as Record<string, string>);
  const data = await fetchApi<any>(`/episodes?${params.toString()}`)
  return <EvidenceClient initialData={data} searchParams={searchParams} />
}

export default function EvidenceBrowserPage({ searchParams }: { searchParams: Record<string, string> }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Evidence Browser</h1>
        <p className="text-muted-foreground mt-2">Filter and read through individual retrieval episodes.</p>
      </div>
      <Suspense fallback={<LoadingState />}>
        <EvidenceData searchParams={searchParams} />
      </Suspense>
    </div>
  )
}
