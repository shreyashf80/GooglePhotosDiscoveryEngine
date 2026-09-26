import { fetchApi } from '@/lib/api'
import GapMatrixClient from './client'
import { Suspense } from 'react'

async function GapData() {
  const data = await fetchApi<any[]>('/gap-matrix')
  return <GapMatrixClient data={data} />
}

export default function GapMatrixPage() {
  return (
    <Suspense fallback={<div className="animate-pulse">Loading gap matrix...</div>}>
      <GapData />
    </Suspense>
  )
}
