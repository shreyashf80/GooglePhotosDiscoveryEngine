import { fetchApi } from '@/lib/api'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ClickableCount } from '@/components/shared/components'
import { PipelineFunnelChart, BreakdownChart } from './client'
import { Suspense } from 'react'
import Link from 'next/link'

async function OverviewData() {
  const overview = await fetchApi<any>('/overview')

  const { kpis, funnel, breakdowns, signal_breakdowns, pipeline_health, top_themes } = overview

  const funnelData = [
    { name: 'Data Collection', value: funnel.raw },
    { name: 'Source Filtering', value: funnel.deduped },
    { name: 'Document Parsing', value: funnel.keyword_pass },
    { name: 'Relevance Filtering', value: funnel.llm_relevant },
    { name: 'Signal Extraction', value: funnel.extracted_signals },
  ]

  const sourceData = breakdowns.source?.map((b: any) => ({ name: b.source || 'Unknown', value: b.count })).sort((a: any, b: any) => b.value - a.value) || []
  const productData = breakdowns.product?.map((b: any) => ({ name: b.product || 'Unknown', value: b.count })).sort((a: any, b: any) => b.value - a.value) || []
  const relevanceData = breakdowns.relevance?.map((b: any) => ({ name: b.relevance_class || 'Unknown', value: b.count })).sort((a: any, b: any) => b.value - a.value) || []

  const coreSignals = signal_breakdowns?.scope?.find((s: any) => s.scope === 'core')?.count || 0
  const adjacentSignals = signal_breakdowns?.scope?.find((s: any) => s.scope === 'adjacent')?.count || 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Overview</h1>
        <p className="text-sm text-gray-500 mt-1">High-level KPIs, funnel metrics, and pipeline health for the Listening V2 discovery engine.</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Total Raw Records</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{kpis.total_records}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Total Filtered / Relevant</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{kpis.relevant_records}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Signals Identified</CardTitle></CardHeader>
          <CardContent>
            <p className="text-3xl font-bold"><ClickableCount count={kpis.total_signals} /></p>
            <p className="text-xs text-gray-500 mt-1">Core: {coreSignals} | Adjacent: {adjacentSignals}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-gray-500">Dropped at Signals</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{funnel.dropped_at_signals}</p></CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PipelineFunnelChart data={funnelData} />
        <Card>
          <CardHeader><CardTitle>Top Core Themes</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-2">Theme</th>
                    <th className="px-4 py-2">Rank Score</th>
                    <th className="px-4 py-2">Scope</th>
                    <th className="px-4 py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {top_themes?.map((t: any) => (
                    <tr key={t.id} className="bg-white border-b hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium">{t.title}</td>
                      <td className="px-4 py-2">{t.rank_score?.toFixed(2)}</td>
                      <td className="px-4 py-2 capitalize">{t.scope}</td>
                      <td className="px-4 py-2">
                        <Link href={`/themes?theme_id=${t.id}`} className="text-blue-600 hover:underline">View</Link>
                      </td>
                    </tr>
                  ))}
                  {(!top_themes || top_themes.length === 0) && (
                    <tr>
                      <td colSpan={4} className="px-4 py-4 text-center text-gray-500">No themes found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <BreakdownChart title="Source Breakdown" description="Records by Source" data={sourceData.slice(0, 5)} />
        <BreakdownChart title="Product Breakdown" description="Records by Product" data={productData.slice(0, 5)} />
        <BreakdownChart title="Relevance Class Breakdown" description="Records by Relevance" data={relevanceData.slice(0, 5)} />
      </div>

      <div className="grid grid-cols-1 gap-6">
        <Card>
          <CardHeader><CardTitle>Pipeline Health (Storage)</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Database Storage Usage</span>
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
    <Suspense fallback={<div className="animate-pulse p-8">Loading overview...</div>}>
      <OverviewData />
    </Suspense>
  )
}
