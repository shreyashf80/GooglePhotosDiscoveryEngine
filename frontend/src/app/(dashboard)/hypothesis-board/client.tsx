'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { EvidenceBadge, ClickableCount, LoadingState } from '@/components/shared/components'
import { Progress } from '@/components/ui/progress'
import { fetchApi } from '@/lib/api'
import { EnumLabel } from '@/components/EnumLabel'

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
  const isAnecdotal = hypothesis.evidence_strength === 'anecdotal'

  const renderH5Chart = (details: any) => {
    if (!details) return null
    const failureModes = ['ui_friction', 'zero_results', 'wrong_results', 'ask_photos_failure', 'other_failure']
    const allCues = new Set([...Object.keys(details.memory || {}), ...Object.keys(details.utility || {})])
    const data = Array.from(allCues)
      .filter(cue => !failureModes.includes(cue))
      .map(cue => ({
        cue,
        memory: details.memory?.[cue] || 0,
        utility: details.utility?.[cue] || 0
      })).sort((a, b) => (b.memory + b.utility) - (a.memory + a.utility)).slice(0, 5)

    return (
      <div className="space-y-2 mt-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium">Top Cues: Memory vs Utility</h4>
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <div className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-purple-500"></div>Memory</div>
            <div className="flex items-center gap-1"><div className="w-2 h-2 rounded bg-blue-500"></div>Utility</div>
          </div>
        </div>
        {data.map(d => (
          <div key={d.cue} className="flex items-center text-xs">
            <span className="w-32 truncate" title={d.cue}><EnumLabel value={d.cue} /></span>
            <div className="flex-1 flex gap-1 h-4">
              <div style={{ width: `${(d.memory / 10) * 100}%` }} className="bg-purple-500 rounded" title={`Memory: ${d.memory}`} />
              <div style={{ width: `${(d.utility / 10) * 100}%` }} className="bg-blue-500 rounded" title={`Utility: ${d.utility}`} />
            </div>
          </div>
        ))}
      </div>
    )
  }

  const renderH6Chart = (details: any) => {
    if (!details) return null
    const buckets = ['under_6m', '6m_1y', '1_3y', '3y_plus']
    return (
      <div className="space-y-2 mt-4">
        <h4 className="text-sm font-medium">Date Imprecision by Photo Age</h4>
        {buckets.map(b => {
          const stats = details[b]
          if (!stats) return null
          const rate = stats.total > 0 ? (stats.imprecision / stats.total) * 100 : 0
          return (
            <div key={b} className="flex items-center text-xs">
              <span className="w-24"><EnumLabel value={b} /></span>
              <div className="flex-1 h-4 bg-gray-100 rounded flex overflow-hidden">
                <div style={{ width: `${rate}%` }} className="bg-amber-500" title={`Imprecise: ${stats.imprecision}/${stats.total}`} />
              </div>
              <span className="w-12 text-right">{rate.toFixed(0)}%</span>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <Card className="mb-4">
      <CardHeader className="cursor-pointer hover:bg-gray-50" onClick={handleExpand}>
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <CardTitle className="text-lg">{hypothesis.hypothesis_id}: {hypothesis.title}</CardTitle>
              <EnumLabel value={hypothesis.status} className={`text-sm font-medium px-2 py-1 rounded capitalize ${
                  hypothesis.status === 'supported' ? 'bg-green-100 text-green-800' :
                  hypothesis.status === 'contradicted' ? 'bg-red-100 text-red-800' :
                  hypothesis.status === 'mixed' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-gray-100 text-gray-800'
                }`} />
            </div>
            <p className="text-sm text-gray-600">{hypothesis.statement}</p>
          </div>
          <div className="text-right text-sm">
            <div><span className="text-gray-500">Relevant:</span> <ClickableCount count={hypothesis.relevant_count} /></div>
          </div>
        </div>
      </CardHeader>
      
      {hypothesis.hypothesis_id === 'H5' ? (
        <CardContent className="border-t pt-4">
          {renderH5Chart(hypothesis.details)}
        </CardContent>
      ) : hypothesis.hypothesis_id === 'H6' ? (
        <CardContent className="border-t pt-4">
          {renderH6Chart(hypothesis.details)}
        </CardContent>
      ) : (
        <CardContent className="border-t pt-4">
           {isAnecdotal ? (
             <div className="flex flex-col items-center gap-1 text-sm mb-2 text-gray-500">
                <div className="w-full h-2 bg-gray-200 rounded" />
                <span className="italic">Too few episodes to judge ({hypothesis.support_count} for, {hypothesis.contradict_count} against)</span>
             </div>
           ) : (
             <div className="flex items-center gap-4 text-sm mb-2">
                <span className="text-green-700 font-medium">Support: {hypothesis.support_count}</span>
                <Progress value={supportPercent} className="h-2 flex-1 [&>div]:bg-green-500 bg-red-100" />
                <span className="text-red-700 font-medium">Contradict: {hypothesis.contradict_count}</span>
             </div>
           )}
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
                      <p className="italic mb-2">&quot;{ep.quote_en}&quot;</p>
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
                      <p className="italic mb-2">&quot;{ep.quote_en}&quot;</p>
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
        <div>
          <h1 className="text-3xl font-bold">Hypothesis Board</h1>
          <p className="text-sm text-gray-500 mt-1">Status of our initial assumptions evaluated against real user episodes.</p>
        </div>
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
