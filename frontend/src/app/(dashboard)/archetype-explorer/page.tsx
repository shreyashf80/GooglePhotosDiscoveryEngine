import { fetchApi } from '@/lib/api'
import ArchetypeClient from './client'
import { Suspense } from 'react'
import { LoadingState } from '@/components/shared/components'

export const revalidate = 300;

async function ArchetypeData({ searchParams }: { searchParams: { a?: string, b?: string } }) {
  const archetypes = await fetchApi<any[]>('/archetypes')
  let comparison = null;
  if (searchParams.a && searchParams.b) {
    comparison = await fetchApi<any>(`/archetypes/compare?a=${searchParams.a}&b=${searchParams.b}`)
  }
  return <ArchetypeClient initialArchetypes={archetypes} comparison={comparison} currentA={searchParams.a} currentB={searchParams.b} />
}

export default function ArchetypeExplorerPage({ searchParams }: { searchParams: { a?: string, b?: string } }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Archetype Explorer</h1>
        <p className="text-muted-foreground mt-2">Compare problem types and prioritize based on opportunity score.</p>
      </div>
      <Suspense fallback={<LoadingState />}>
        <ArchetypeData searchParams={searchParams} />
      </Suspense>
    </div>
  )
}
