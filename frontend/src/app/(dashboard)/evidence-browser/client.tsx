'use client';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EnumLabel } from '@/components/EnumLabel';
import { ChevronDown, ChevronUp, Download, AlertCircle } from 'lucide-react';

function SignalRow({ signal }: { signal: any }) {
  const [expanded, setExpanded] = useState(false);

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
            <p className="font-medium text-gray-900">{signal.summary_en}</p>
            {signal.emotional_cost && signal.emotional_cost !== 'none' && signal.emotional_cost !== 'unknown' && (
              <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200 ml-2 whitespace-nowrap">
                <AlertCircle className="h-3 w-3 mr-1" /> {signal.emotional_cost}
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {signal.theme_name && <Badge variant="secondary">{signal.theme_name}</Badge>}
            <Badge variant="outline"><EnumLabel value={signal.scope} /></Badge>
            {signal.outcome && <Badge variant="outline"><EnumLabel value={signal.outcome} /></Badge>}
            <span className="text-gray-500 ml-auto flex items-center gap-2">
              <EnumLabel value={signal.source} /> &bull; {new Date(signal.created_at).toLocaleDateString()}
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
                  "{signal.quote_en}"
                </div>
                {signal.quote_original && signal.quote_original !== signal.quote_en && (
                  <div className="p-3 bg-white border rounded text-sm text-gray-600 italic">
                    Original ({signal.lang}): "{signal.quote_original}"
                  </div>
                )}
              </div>
              {signal.url && (
                <div className="mt-3">
                  <a href={signal.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-sm font-medium">
                    View original post ↗
                  </a>
                </div>
              )}
            </div>
            
            <div className="space-y-4">
              {signal.remembered && signal.remembered.length > 0 && (
                <div>
                  <h4 className="font-semibold text-sm text-gray-700 mb-1">Remembered Cues</h4>
                  <ul className="list-disc pl-4 text-sm space-y-1">
                    {signal.remembered.map((c: string, idx: number) => (
                      <li key={idx} className="text-gray-700">{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {signal.forgot && signal.forgot.length > 0 && (
                <div>
                  <h4 className="font-semibold text-sm text-gray-700 mb-1">Forgotten Cues</h4>
                  <ul className="list-disc pl-4 text-sm space-y-1">
                    {signal.forgot.map((c: string, idx: number) => (
                      <li key={idx} className="text-gray-700">{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function EvidenceClient({ initialData, themes = [], searchParams }: { initialData: any, themes?: any[], searchParams: Record<string, string> }) {
  const router = useRouter();

  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.delete('page');
    router.push(`?${params.toString()}`);
  };

  const handleExport = () => {
    const params = new URLSearchParams(searchParams);
    window.open(`/api/signals/export?${params.toString()}`, '_blank');
  };

  const { items = [], total = 0, page = 1, per_page = 20 } = initialData || {};
  const currentPage = Number(page);
  const totalPages = Math.ceil(total / per_page);

  return (
    <div className="space-y-6">
      <div className="bg-white p-4 rounded-md border space-y-4">
        <div className="grid grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Scope</label>
            <select className="w-full border rounded p-2 text-sm" value={searchParams.scope || ''} onChange={e => updateFilter('scope', e.target.value)}>
              <option value="">All</option>
              <option value="core">Core</option>
              <option value="adjacent">Adjacent</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Theme</label>
            <select className="w-full border rounded p-2 text-sm" value={searchParams.theme || ''} onChange={e => updateFilter('theme', e.target.value)}>
              <option value="">All</option>
              {themes.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Relevance Class</label>
            <select className="w-full border rounded p-2 text-sm" value={searchParams.relevance_class || ''} onChange={e => updateFilter('relevance_class', e.target.value)}>
              <option value="">All</option>
              <option value="success_or_tip">Success / Tip</option>
              <option value="struggle">Struggle</option>
              <option value="failure">Failure</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Source</label>
            <input 
              type="text" 
              className="w-full border rounded p-2 text-sm" 
              placeholder="e.g. reddit" 
              value={searchParams.source || ''} 
              onChange={e => updateFilter('source', e.target.value)} 
            />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Product</label>
            <input 
              type="text" 
              className="w-full border rounded p-2 text-sm" 
              placeholder="e.g. google_photos" 
              value={searchParams.product || ''} 
              onChange={e => updateFilter('product', e.target.value)} 
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Funnel Stage</label>
            <input 
              type="text" 
              className="w-full border rounded p-2 text-sm" 
              placeholder="e.g. search" 
              value={searchParams.funnel_stage || ''} 
              onChange={e => updateFilter('funnel_stage', e.target.value)} 
            />
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
          <div className="pb-0 self-end">
            <Button variant="outline" onClick={handleExport} className="w-full flex items-center justify-center gap-2">
              <Download className="h-4 w-4" /> Export
            </Button>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-600">
        <div>Showing {items.length} of {total} signals</div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={currentPage <= 1} onClick={() => updateFilter('page', String(currentPage - 1))}>Previous</Button>
          <span>Page {currentPage} of {totalPages || 1}</span>
          <Button variant="outline" size="sm" disabled={currentPage >= totalPages || totalPages === 0} onClick={() => updateFilter('page', String(currentPage + 1))}>Next</Button>
        </div>
      </div>

      <div className="space-y-4">
        {items.map((signal: any) => (
          <SignalRow key={signal.signal_id || signal.record_id} signal={signal} />
        ))}
        {items.length === 0 && (
          <div className="p-8 text-center text-gray-500 border rounded-md bg-gray-50">No signals match your filters.</div>
        )}
      </div>
    </div>
  )
}
