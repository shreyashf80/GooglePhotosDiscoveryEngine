import { fetchApi } from '@/lib/api'
import SegmentClient from './client'
import { Suspense } from 'react'
import { LoadingState } from '@/components/shared/components'

export const revalidate = 300;

async function SegmentData({ dimension }: { dimension: string }) {
  const segments = await fetchApi<any[]>(`/segments?dimension=${dimension}`)
  return <SegmentClient initialSegments={segments} currentDimension={dimension} />
}

export default function SegmentExplorerPage({ searchParams }: { searchParams: { dimension?: string } }) {
  const dimension = searchParams.dimension || 'source';
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Segment Explorer</h1>
        <p className="text-muted-foreground mt-2">Which user groups hit which problems?</p>
      </div>
      <Suspense fallback={<LoadingState />}>
        <SegmentData dimension={dimension} />
      </Suspense>
    </div>
  )
}
