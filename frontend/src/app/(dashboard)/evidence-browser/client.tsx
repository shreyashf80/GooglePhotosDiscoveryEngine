'use client';
import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EnumLabel } from '@/components/EnumLabel';
import { AlertTriangle, ChevronDown, ChevronUp, Download } from 'lucide-react';
import { fetchApi } from '@/lib/api';

function EpisodeRow({ ep }: { ep: any }) {
  const [expanded, setExpanded] = useState(false);
  const [details, setDetails] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (expanded && !details && !loading) {
      setLoading(true);
      fetchApi<any>(`/episodes/${ep.episode_id}`)
        .then(data => setDetails(data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [expanded, details, loading, ep.episode_id]);

  const isLowConfidence = ep.extraction_confidence === 'low';

  return (
    <div className="border rounded-md bg-white overflow-hidden">
      <div 
        className="p-4 cursor-pointer hover:bg-gray-50 flex gap-4 items-start"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="mt-1 text-gray-500">
          {expanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </div>
        <div className="flex-1 space-y-2">
          <div className="flex items-start justify-between">
            <p className="font-medium text-gray-900">{ep.summary_en}</p>
            {isLowConfidence && (
              <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-200 ml-2 whitespace-nowrap">
                <AlertTriangle className="h-3 w-3 mr-1" /> Low Confidence
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge variant="secondary"><EnumLabel value={ep.archetype_primary} /></Badge>
            <Badge variant="outline"><EnumLabel value={ep.photo_category} /></Badge>
            <Badge variant="outline"><EnumLabel value={ep.outcome} /></Badge>
            <span className="text-gray-500 ml-auto flex items-center gap-2">
              <EnumLabel value={ep.source} /> &bull; {new Date(ep.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>
      
      {expanded && (
        <div className="border-t bg-gray-50 p-6 space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h4 className="font-semibold text-sm text-gray-700 mb-2">Quotes</h4>
              <div className="space-y-3">
                <div className="p-3 bg-white border rounded text-sm text-gray-800 italic">
                  "{ep.quote_en}"
                </div>
                {ep.quote_original && ep.quote_original !== ep.quote_en && (
                  <div className="p-3 bg-white border rounded text-sm text-gray-600 italic">
                    Original ({ep.lang}): "{ep.quote_original}"
                  </div>
                )}
              </div>
              {ep.url && (
                <div className="mt-3">
                  <a href={ep.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-sm font-medium">
                    View original post ↗
                  </a>
                </div>
              )}
            </div>
            
            <div className="space-y-4">
              {loading && <div className="text-sm text-gray-500 animate-pulse">Loading details...</div>}
              
              {details && (
                <>
                  {details.cues?.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-sm text-gray-700 mb-1">Remembered Cues</h4>
                      <ul className="list-disc pl-4 text-sm space-y-1">
                        {details.cues.map((c: any) => (
                          <li key={c.id}>
                            <EnumLabel value={c.cue_type} />: <span className="font-medium">"{c.value}"</span> <span className="text-gray-500">({c.precision})</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {details.queries?.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-sm text-gray-700 mb-1">Queries Tried</h4>
                      <ol className="list-decimal pl-4 text-sm space-y-1">
                        {details.queries.map((q: any) => (
                          <li key={q.id}>
                            <span className="font-medium">"{q.query_text}"</span> <span className="text-gray-500">(<EnumLabel value={q.query_style} />)</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </>
              )}
              
              {ep.failure_modes?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-sm text-gray-700 mb-1">Failure Modes</h4>
                  <div className="flex flex-wrap gap-1">
                    {ep.failure_modes.map((f: string) => (
                      <span key={f} className="text-xs bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 rounded">
                        <EnumLabel value={f} />
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {ep.workarounds?.length > 0 && (
                <div>
                  <h4 className="font-semibold text-sm text-gray-700 mb-1">Workarounds</h4>
                  <div className="flex flex-wrap gap-1">
                    {ep.workarounds.map((w: string) => (
                      <span key={w} className="text-xs bg-gray-200 text-gray-800 border px-2 py-0.5 rounded">
                        <EnumLabel value={w} />
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function EvidenceClient({ initialData, searchParams }: { initialData: any, searchParams: Record<string, string> }) {
  const router = useRouter();

  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.delete('page'); // reset to page 1 on filter change
    router.push(`?${params.toString()}`);
  };

  const handleExport = () => {
    const params = new URLSearchParams(searchParams);
    // Assuming backend returns CSV when hitting export endpoint
    window.open(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/api/v1/episodes/export?${params.toString()}`, '_blank');
  };

  const { items, total, page, per_page } = initialData;
  const totalPages = Math.ceil(total / per_page);

  return (
    <div className="space-y-6">
      <div className="bg-white p-4 rounded-md border grid grid-cols-4 gap-4 items-end">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Archetype</label>
          <select className="w-full border rounded p-2 text-sm" value={searchParams.archetype || ''} onChange={e => updateFilter('archetype', e.target.value)}>
            <option value="">All</option>
            <option value="utility_lookup">Utility Lookup</option>
            <option value="needle_in_flood">Needle in Flood</option>
            <option value="provenance_lost">Provenance Lost</option>
            <option value="refinement_dead_end">Refinement Dead End</option>
            <option value="vocabulary_mismatch">Vocabulary Mismatch</option>
            <option value="time_drift">Time Drift</option>
            <option value="emergent">Emergent</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Category</label>
          <select className="w-full border rounded p-2 text-sm" value={searchParams.category || ''} onChange={e => updateFilter('category', e.target.value)}>
            <option value="">All</option>
            <option value="document_text">Document/Text</option>
            <option value="people_moment">People Moment</option>
            <option value="pet_animal">Pet/Animal</option>
            <option value="travel_place">Travel/Place</option>
            <option value="meme_forward">Meme/Forward</option>
            <option value="health_medical">Health/Medical</option>
            <option value="other">Other</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Outcome</label>
          <select className="w-full border rounded p-2 text-sm" value={searchParams.outcome || ''} onChange={e => updateFilter('outcome', e.target.value)}>
            <option value="">All</option>
            <option value="found_easily">Found Easily</option>
            <option value="found_with_effort">Found With Effort</option>
            <option value="still_searching">Still Searching</option>
            <option value="gave_up">Gave Up</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-700 mb-1">Search text</label>
            <input 
              type="text" 
              className="w-full border rounded p-2 text-sm" 
              placeholder="Search summaries..." 
              value={searchParams.search || ''} 
              onChange={e => updateFilter('search', e.target.value)} 
            />
          </div>
          <div className="pb-0 self-end">
            <Button variant="outline" onClick={handleExport} className="w-full flex items-center justify-center gap-2">
              <Download className="h-4 w-4" /> Export CSV
            </Button>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-600">
        <div>Showing {items.length} of {total} episodes</div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => updateFilter('page', String(page - 1))}>Previous</Button>
          <span>Page {page} of {totalPages || 1}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => updateFilter('page', String(page + 1))}>Next</Button>
        </div>
      </div>

      <div className="space-y-4">
        {items.map((ep: any) => (
          <EpisodeRow key={ep.episode_id} ep={ep} />
        ))}
        {items.length === 0 && (
          <div className="p-8 text-center text-gray-500 border rounded-md bg-gray-50">No episodes match your filters.</div>
        )}
      </div>
    </div>
  )
}
