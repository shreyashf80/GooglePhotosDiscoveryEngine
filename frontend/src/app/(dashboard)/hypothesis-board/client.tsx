'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { EvidenceBadge, ClickableCount, LoadingState } from '@/components/shared/components'
import { Progress } from '@/components/ui/progress'
import { fetchApi } from '@/lib/api'

function HypothesisCard({ hypothesis }: { hypothesis: any }) {
  const [expanded, setExpanded] = useState(false)
  const [details, setDetails] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const handleExpand = async () => {
    setExpanded(!expanded)
    if (!expanded && !details) {
      setLoading(true)
      try {
        const data = await fetchApi<any>(`/hypotheses/${hypothesis.hypothesis_id}`)
        setDetails(data)
      } finally {
        setLoading(false)
      }
    }
  }

  const totalVotes = hypothesis.support_count + hypothesis.contradict_count
  const supportPercent = totalVotes > 0 ? (hypothesis.support_count / totalVotes) * 100 : 0

  return (
    <Card className="mb-4">
      <CardHeader className="cursor-pointer hover:bg-gray-50" onClick={handleExpand}>
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <CardTitle className="text-lg">{hypothesis.hypothesis_id}: {hypothesis.title}</CardTitle>
              <EvidenceBadge strength={hypothesis.evidence_strength || 'anecdotal'} />
              <span className="text-sm font-medium px-2 py-1 bg-gray-100 rounded text-gray-700 capitalize">
                {hypothesis.status}
              </span>
            </div>
            <p className="text-sm text-gray-600">{hypothesis.statement}</p>
          </div>
          <div className="text-right text-sm">
            <div><span className="text-gray-500">Relevant:</span> <ClickableCount count={hypothesis.relevant_count} /></div>
          </div>
        </div>
      </CardHeader>
      
      {(hypothesis.hypothesis_id === 'H5' || hypothesis.hypothesis_id === 'H6') && hypothesis.details ? (
        <CardContent className="border-t pt-4">
          <p className="text-sm italic text-gray-500 mb-2">Distribution Chart Placeholders</p>
          <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">
            {JSON.stringify(hypothesis.details, null, 2)}
          </pre>
        </CardContent>
      ) : (
        <CardContent className="border-t pt-4">
           <div className="flex items-center gap-4 text-sm mb-2">
              <span className="text-green-700 font-medium">Support: {hypothesis.support_count}</span>
              <Progress value={supportPercent} className="h-2 flex-1" />
              <span className="text-red-700 font-medium">Contradict: {hypothesis.contradict_count}</span>
           </div>
        </CardContent>
      )}

      {expanded && (
        <CardContent className="bg-gray-50 pt-4 border-t">
          {loading ? (
            <LoadingState />
          ) : details ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-semibold text-green-700 mb-3 border-b pb-1">Top Supporting Evidence</h4>
                <div className="space-y-4">
                  {details.support_evidence?.map((ep: any) => (
                    <div key={ep.episode_id} className="text-sm bg-white p-3 rounded shadow-sm border">
                      <p className="italic mb-2">"{ep.quote_en}"</p>
                      <div className="text-xs text-gray-500 flex justify-between">
                        <span>Rank: {ep.rank} | Conf: {ep.extraction_confidence}</span>
                        <a href={ep.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">Source</a>
                      </div>
                    </div>
                  ))}
                  {!details.support_evidence?.length && <p className="text-sm text-gray-500">None found</p>}
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-red-700 mb-3 border-b pb-1">Top Contradicting Evidence</h4>
                <div className="space-y-4">
                  {details.contradict_evidence?.map((ep: any) => (
                    <div key={ep.episode_id} className="text-sm bg-white p-3 rounded shadow-sm border">
                      <p className="italic mb-2">"{ep.quote_en}"</p>
                      <div className="text-xs text-gray-500 flex justify-between">
                        <span>Rank: {ep.rank} | Conf: {ep.extraction_confidence}</span>
                        <a href={ep.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">Source</a>
                      </div>
                    </div>
                  ))}
                  {!details.contradict_evidence?.length && <p className="text-sm text-gray-500">None found</p>}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-red-500">Failed to load details.</p>
          )}
        </CardContent>
      )}
    </Card>
  )
}

export default function HypothesisBoardClient({ hypotheses, emergent }: { hypotheses: any[], emergent: any[] }) {
  const [sortBy, setSortBy] = useState<'id' | 'status' | 'strength'>('id')

  const sorted = [...hypotheses].sort((a, b) => {
    if (sortBy === 'status') return a.status.localeCompare(b.status)
    if (sortBy === 'strength') return (b.support_count + b.contradict_count) - (a.support_count + a.contradict_count)
    return a.hypothesis_id.localeCompare(b.hypothesis_id)
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <h1 className="text-3xl font-bold">Hypothesis Board</h1>
        <div className="space-x-2">
          <span className="text-sm text-gray-500">Sort by:</span>
          <select 
            className="text-sm border rounded px-2 py-1"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
          >
            <option value="id">ID</option>
            <option value="status">Status</option>
            <option value="strength">Relevant Count</option>
          </select>
        </div>
      </div>

      <div className="space-y-4">
        {sorted.map(h => <HypothesisCard key={h.hypothesis_id} hypothesis={h} />)}
      </div>

      <Card>
        <CardHeader><CardTitle>Emergent Patterns</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {emergent.map((e: any) => (
              <span key={e.label} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-50 text-purple-700 border border-purple-200 text-sm">
                {e.label} <span className="font-bold bg-white px-1.5 rounded-full text-xs">{e.episode_count}</span>
              </span>
            ))}
            {emergent.length === 0 && <span className="text-sm text-gray-500">No emergent patterns identified yet.</span>}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
