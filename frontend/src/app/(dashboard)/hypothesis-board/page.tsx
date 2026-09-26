import { fetchApi } from '@/lib/api'
import HypothesisBoardClient from './client'
import { Suspense } from 'react'

async function HypothesisData() {
  const [hypotheses, emergent] = await Promise.all([
    fetchApi<any[]>('/hypotheses'),
    fetchApi<any[]>('/emergent-labels').catch(() => [])
  ])
  
  return <HypothesisBoardClient hypotheses={hypotheses} emergent={emergent} />
}

export default function HypothesisBoardPage() {
  return (
    <Suspense fallback={<div className="animate-pulse">Loading hypotheses...</div>}>
      <HypothesisData />
    </Suspense>
  )
}
