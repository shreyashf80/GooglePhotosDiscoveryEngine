import { fetchApi } from '@/lib/api'
import EvidenceClient from './client'
import { Suspense } from 'react'
import { LoadingState } from '@/components/shared/components'

export const revalidate = 300;

async function EvidenceData({ searchParams }: { searchParams: Record<string, string> }) {
  const queryObj: Record<string, string> = {};
  if (searchParams && typeof searchParams === 'object') {
    for (const [k, v] of Object.entries(searchParams)) {
      if (typeof v === 'string') {
        queryObj[k] = v;
      }
    }
  }
  const params = new URLSearchParams(queryObj);
  const data = await fetchApi<any>(`/signals?${params.toString()}`);
  const themes = await fetchApi<any[]>('/themes').catch(() => []);
  return <EvidenceClient initialData={data} themes={themes} searchParams={queryObj} />
}

export default async function EvidenceBrowserPage({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const resolvedParams = (await searchParams) || {};
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Evidence Browser</h1>
        <p className="text-muted-foreground mt-2">Filter and read through individual retrieval episodes.</p>
      </div>
      <Suspense fallback={<LoadingState />}>
        <EvidenceData searchParams={resolvedParams} />
      </Suspense>
    </div>
  )
}
