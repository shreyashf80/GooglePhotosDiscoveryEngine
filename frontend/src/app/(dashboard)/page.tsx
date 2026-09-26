import { fetchApi } from '@/lib/api'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ClickableCount } from '@/components/shared/components'
import { PipelineFunnelChart, RetrievalFunnelChart } from './client'
import { Suspense } from 'react'

async function OverviewData() {
  const [overview, funnelStats] = await Promise.all([
    fetchApi<any>('/overview'),
    fetchApi<any[]>('/funnel').catch(() => [])
  ])

  const { kpis, funnel, breakdowns, sufficiency, pipeline_health } = overview

  const funnelData = [
    { name: 'Raw', value: funnel.raw },
    { name: 'Deduped', value: funnel.deduped },
    { name: 'Keyword Hit', value: funnel.keyword_pass },
    { name: 'Relevant', value: funnel.llm_relevant },
    { name: 'Episodes', value: funnel.extracted_episodes },
  ]

  const retrievalFunnelData = funnelStats.map(f => ({
    name: f.stage,
    Episodes: f.episode_count,
    Complaints: f.general_complaint_count,
    GaveUpRate: Math.round(f.gave_up_rate * 100)
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Overview</h1>
        <p className="text-sm text-gray-500 mt-1">High-level KPIs, funnel metrics, and pipeline health for the discovery engine.</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Total Records</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{kpis.total_records}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Relevant Records</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{kpis.relevant_records}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Extracted Episodes</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold"><ClickableCount count={kpis.total_episodes} /></p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Success/Tip Records</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{kpis.success_tip_records}</p></CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PipelineFunnelChart data={funnelData} />
        <RetrievalFunnelChart data={retrievalFunnelData} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle>Data Sufficiency (Target: 120 Episodes)</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Episodes: {kpis.total_episodes}</span>
                <span>Target: 120</span>
              </div>
              <Progress value={Math.min((kpis.total_episodes / 120) * 100, 100)} className="h-2" />
            </div>
            <div>
              <h4 className="font-medium text-sm mt-4 mb-2">Hypotheses by Evidence Strength</h4>
              <ul className="space-y-1 text-sm">
                {sufficiency.map((s: any) => (
                  <li key={s.evidence_strength} className="flex justify-between">
                    <span className="capitalize">{s.evidence_strength || 'Unknown'}</span>
                    <span className="font-medium">{s.count}</span>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Pipeline Health</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span>Failed Extractions</span>
              <span className="font-medium text-red-600">{pipeline_health.failed_records}</span>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Database Storage</span>
                <span>{(pipeline_health.storage_bytes / 1024 / 1024).toFixed(1)} MB / 500 MB</span>
              </div>
              <Progress 
                value={Math.min((pipeline_health.storage_bytes / (500 * 1024 * 1024)) * 100, 100)} 
                className={`h-2 ${pipeline_health.storage_bytes > 400 * 1024 * 1024 ? 'bg-red-200' : pipeline_health.storage_bytes > 300 * 1024 * 1024 ? 'bg-amber-200' : ''}`}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default function OverviewPage() {
  return (
    <Suspense fallback={<div className="animate-pulse">Loading overview...</div>}>
      <OverviewData />
    </Suspense>
  )
}
