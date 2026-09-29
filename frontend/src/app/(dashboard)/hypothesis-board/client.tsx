'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'

export default function HypothesisBoardClient({ hypotheses }: { hypotheses: any[] }) {
  const [scope, setScope] = useState<'core' | 'adjacent'>('core')
  const [stageFilter, setStageFilter] = useState<string>('all')

  const stages = Array.from(new Set(hypotheses.map(h => h.details?.stage).filter(Boolean))) as string[]

  const filtered = hypotheses.filter(h => {
    if (h.scope !== scope) return false
    if (stageFilter !== 'all' && h.details?.stage !== stageFilter) return false
    return true
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold">Hypothesis Board</h1>
          <p className="text-sm text-gray-500 mt-1">Dynamic data-derived hypotheses from user episodes.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="space-x-2 flex items-center">
            <span className="text-sm text-gray-500">Stage:</span>
            <select 
              className="text-sm border rounded px-2 py-1 bg-white"
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
            >
              <option value="all">All Stages</option>
              {stages.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
      </div>

      <Tabs value={scope} onValueChange={(v) => setScope(v as 'core' | 'adjacent')}>
        <TabsList>
          <TabsTrigger value="core">Core Scope</TabsTrigger>
          <TabsTrigger value="adjacent">Adjacent Scope</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {filtered.map(h => (
          <Card key={h.hypothesis_id} className="flex flex-col shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-3 border-b bg-gray-50/50">
              <div className="flex justify-between items-start gap-3 mb-3">
                <CardTitle className="text-lg leading-snug font-bold">{h.title}</CardTitle>
                {h.details?.stage && (
                  <Badge variant="outline" className="shrink-0 bg-white capitalize">
                    {h.details.stage.replace(/_/g, ' ')}
                  </Badge>
                )}
              </div>
              <p className="text-sm font-medium text-gray-900 border-l-2 border-blue-500 pl-3 italic">
                {h.statement}
              </p>
            </CardHeader>
            <CardContent className="pt-4 flex-1 flex flex-col gap-5 text-sm">
              <div>
                <h4 className="font-semibold text-green-700 mb-1 flex items-center gap-1.5">
                  <span className="text-lg leading-none">•</span> Why We Believe It
                </h4>
                <p className="text-gray-700 leading-relaxed">{h.details?.why || 'N/A'}</p>
              </div>
              
              <div>
                <h4 className="font-semibold text-amber-700 mb-1 flex items-center gap-1.5">
                  <span className="text-lg leading-none">•</span> Counter-Evidence
                </h4>
                <p className="text-gray-700 leading-relaxed">{h.details?.counter || 'None identified'}</p>
              </div>

              <div>
                <h4 className="font-semibold text-red-700 mb-1 flex items-center gap-1.5">
                  <span className="text-lg leading-none">•</span> What Would Disprove It
                </h4>
                <p className="text-gray-700 leading-relaxed">{h.details?.disprove || 'N/A'}</p>
              </div>

              <div className="mt-auto pt-4 border-t border-dashed">
                <h4 className="font-semibold text-blue-800 mb-2">Recommended Research Question</h4>
                <div className="bg-blue-50 text-blue-900 p-3 rounded text-sm font-medium border border-blue-100">
                  {h.research_question || 'N/A'}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full py-16 text-center text-gray-500 bg-gray-50 rounded-lg border border-dashed">
            No hypotheses found for the selected filters.
          </div>
        )}
      </div>
    </div>
  )
}
