import { fetchApi } from '@/lib/api'
import HypothesisBoardClient from './client'
import { Suspense } from 'react'

async function HypothesisData() {
  const hypotheses = await fetchApi<any[]>('/hypotheses')
  
  return <HypothesisBoardClient hypotheses={hypotheses} />
}

export default function HypothesisBoardPage() {
  return (
    <Suspense fallback={<div className="animate-pulse">Loading hypotheses...</div>}>
      <HypothesisData />
    </Suspense>
  )
}
