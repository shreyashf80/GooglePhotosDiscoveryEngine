'use client';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EvidenceBadge, ClickableCount } from '@/components/shared/components';
import { EnumLabel } from '@/components/EnumLabel';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { InfoIcon } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function ArchetypeClient({ initialArchetypes, emergentLabels, comparison, currentA, currentB }: { initialArchetypes: any[], emergentLabels?: any[], comparison: any, currentA?: string, currentB?: string }) {
  const router = useRouter();

  const handleCompareChange = (key: 'a' | 'b', value: string) => {
    const params = new URLSearchParams(window.location.search);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    router.push(`?${params.toString()}`);
  }

  const isComparing = currentA && currentB;
  const maxShare = Math.max(...initialArchetypes.map(a => a.share_of_episodes || 0));

  return (
    <div className="space-y-8">
      <div className="flex gap-4 items-center p-4 bg-white border rounded-md">
        <span className="font-medium">Compare mode:</span>
        <select 
          className="border rounded p-1" 
          value={currentA || ''} 
          onChange={(e) => handleCompareChange('a', e.target.value)}
        >
          <option value="">Select archetype A...</option>
          {initialArchetypes.map(a => <option key={a.archetype} value={a.archetype}>{a.archetype}</option>)}
        </select>
        <span>vs</span>
        <select 
          className="border rounded p-1" 
          value={currentB || ''} 
          onChange={(e) => handleCompareChange('b', e.target.value)}
        >
          <option value="">Select archetype B...</option>
          {initialArchetypes.map(a => <option key={a.archetype} value={a.archetype}>{a.archetype}</option>)}
        </select>
      </div>

      {!isComparing ? (
        <div className="space-y-4">
          <div className="flex justify-end items-center text-sm text-gray-500">
            <Popover>
              <PopoverTrigger className="flex items-center gap-1 hover:text-gray-900">
                <InfoIcon className="h-4 w-4" /> Score formula
              </PopoverTrigger>
              <PopoverContent className="w-80 text-sm">
                <p><strong>Opportunity Score</strong> = share_of_episodes × avg_severity × avg_stakes_weight</p>
                <p className="text-gray-500 mt-1">Normalized to 0-100 across all archetypes. Higher score indicates a bigger opportunity to improve user experience.</p>
              </PopoverContent>
            </Popover>
          </div>
          {initialArchetypes.filter(arch => arch.archetype !== 'emergent').map((arch) => (
            <Card key={arch.archetype}>
              <CardContent className="flex items-center justify-between p-6">
                <div>
                  <h3 className="text-lg font-bold"><EnumLabel value={arch.archetype} /></h3>
                  <div className="flex gap-4 text-sm text-gray-500 mt-1">
                    <span>Episodes: <ClickableCount count={arch.episode_count} param="archetype" value={arch.archetype} /></span>
                    <span>Severity: {arch.avg_severity?.toFixed(1)}</span>
                    <span>Stakes: {arch.avg_stakes_weight?.toFixed(1)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right flex flex-col items-end">
                    <div className="text-2xl font-bold flex items-baseline gap-2">
                      {Math.round(arch.opportunity_score)}
                      <span className="text-[11px] font-normal text-gray-400">based on {arch.episode_count} episodes</span>
                    </div>
                    <div className="text-xs text-gray-500">Opportunity Score</div>
                  </div>
                  <EvidenceBadge strength={arch.evidence_strength} />
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Emergent (Unclassified Patterns) Section */}
          {(() => {
            const emergent = initialArchetypes.find(a => a.archetype === 'emergent');
            if (!emergent) return null;
            return (
              <div className="mt-8">
                <h3 className="text-xl font-semibold mb-4">Unclassified Patterns</h3>
                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-lg font-bold text-gray-700">Emergent</h3>
                        <div className="flex gap-4 text-sm text-gray-500 mt-1">
                          <span>Episodes: <ClickableCount count={emergent.episode_count} param="archetype" value={emergent.archetype} /></span>
                          <span>Severity: {emergent.avg_severity?.toFixed(1)}</span>
                          <span>Stakes: {emergent.avg_stakes_weight?.toFixed(1)}</span>
                        </div>
                      </div>
                      <EvidenceBadge strength={emergent.evidence_strength} />
                    </div>
                    {emergentLabels && emergentLabels.length > 0 && (
                      <div className="mt-4">
                        <h4 className="text-sm font-semibold mb-2">Discovered Labels</h4>
                        <div className="flex flex-wrap gap-2">
                          {emergentLabels.map((lbl, idx) => (
                            <Badge key={idx} variant="secondary">
                              {lbl.emergent_label} ({lbl.episode_count})
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            );
          })()}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-8">
          {[comparison?.a, comparison?.b].map((side, i) => {
            if (!side?.stats) return <div key={i}>Loading side...</div>;
            const stats = side.stats;
            const topOutcomes = Object.entries(stats.outcome_distribution || {}).map(([k, v]) => ({ name: k, value: v }));
            
            return (
              <div key={i} className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-xl"><EnumLabel value={stats.archetype} /></CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div>
                      <h4 className="font-semibold mb-2">Outcome Distribution</h4>
                      <div className="h-48">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={topOutcomes} layout="vertical" margin={{ left: 80 }}>
                            <XAxis type="number" />
                            <YAxis dataKey="name" type="category" tickFormatter={(v) => v.replace(/_/g, ' ')} />
                            <Tooltip />
                            <Bar dataKey="value" fill="#3b82f6" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <h4 className="font-semibold mb-1">Top Cues</h4>
                        <ul className="list-disc pl-4">
                          {(stats.top_cue_types || []).slice(0, 3).map((c: any, i: number) => (
                            <li key={i}><EnumLabel value={c.cue_type} /> ({c.count})</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4 className="font-semibold mb-1">Top Failures</h4>
                        <ul className="list-disc pl-4">
                          {(stats.top_failure_modes || []).slice(0, 3).map((f: any, i: number) => (
                            <li key={i}><EnumLabel value={f.failure_mode} /> ({f.count})</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                    
                    <div>
                      <h4 className="font-semibold mb-2">Representative Quotes</h4>
                      <div className="space-y-3">
                        {(side.quotes || []).slice(0, 3).map((q: any, i: number) => (
                          <div key={i} className="text-sm bg-gray-50 p-3 rounded italic border text-gray-700">
                            "{q.quote_en}"
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
