'use client';
import { useRouter } from 'next/navigation';
import { EnumLabel } from '@/components/EnumLabel';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { ClickableCount } from '@/components/shared/components';

export default function SegmentClient({ initialSegments, currentDimension }: { initialSegments: any[], currentDimension: string }) {
  const router = useRouter();
  
  const dimensions = [
    { id: 'source', label: 'Source' },
    { id: 'product', label: 'Product' },
    { id: 'class', label: 'Relevance Class' },
    { id: 'language', label: 'Language' },
  ];

  const handleDimensionChange = (val: string) => {
    router.push(`?dimension=${val}`);
  }

  // Extract unique themes and dimension values
  const themes = Array.from(new Set(initialSegments.map(s => s.archetype))).sort();
  const values = Array.from(new Set(initialSegments.map(s => s.value))).sort();

  // Helper to map 0-1 gave_up_rate to a color intensity
  const getHeatmapColor = (rate: number, count: number) => {
    if (count < 10) return 'bg-gray-100 text-gray-400 border-gray-200'; // anecdotal
    
    // Scale from light red to dark red based on rate
    if (rate > 0.75) return 'bg-red-500 text-white border-red-600';
    if (rate > 0.5) return 'bg-red-400 text-white border-red-500';
    if (rate > 0.25) return 'bg-red-300 text-red-900 border-red-400';
    if (rate > 0) return 'bg-red-200 text-red-800 border-red-300';
    return 'bg-red-50 text-red-700 border-red-100';
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-4 items-center p-4 bg-white border rounded-md">
        <span className="font-medium">Dimension:</span>
        <select 
          className="border rounded p-1" 
          value={currentDimension} 
          onChange={(e) => handleDimensionChange(e.target.value)}
        >
          {dimensions.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}
        </select>
      </div>

      <div className="border rounded-md overflow-x-auto bg-white">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 font-semibold text-gray-900 sticky left-0 bg-gray-50 border-r z-10 w-48">Theme</th>
              {values.map(val => (
                <th key={val} className="px-4 py-3 font-semibold text-gray-900 text-center min-w-[120px]">
                  <EnumLabel value={val} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {themes.map((theme, idx) => (
              <tr key={theme} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900 sticky left-0 bg-white border-r z-10 truncate" title={theme}>
                  <EnumLabel value={theme} />
                </td>
                {values.map(val => {
                  const cell = initialSegments.find(s => s.archetype === theme && s.value === val);
                  if (!cell) {
                    return <td key={val} className="px-4 py-3 text-center text-gray-300">-</td>;
                  }
                  
                  const count = cell.episode_count || cell.counts || 0;
                  const gaveUpRate = cell.outcome_mix?.gave_up ? cell.outcome_mix.gave_up / count : 0;
                  const isAnecdotal = count < 10;
                  
                  return (
                    <td key={val} className="p-2">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger className={`p-3 w-full rounded-md text-center border font-semibold flex flex-col justify-center items-center h-16 ${getHeatmapColor(gaveUpRate, count)}`}>
                            <ClickableCount count={count} filters={{ theme: theme, [currentDimension === 'class' ? 'relevance_class' : currentDimension]: val }} />
                            {isAnecdotal && <span className="text-[10px] mt-1 opacity-70 font-normal uppercase tracking-wider">Anecdotal</span>}
                          </TooltipTrigger>
                          <TooltipContent>
                            <div className="text-xs space-y-1">
                              <p><strong>Theme:</strong> {theme}</p>
                              <p><strong>{dimensions.find(d => d.id === currentDimension)?.label}:</strong> {val}</p>
                              <p><strong>Episodes:</strong> {count}</p>
                              {!isAnecdotal && <p><strong>Gave-up rate:</strong> {(gaveUpRate * 100).toFixed(0)}%</p>}
                              {isAnecdotal && <p className="text-gray-400 italic">Too few episodes to calculate reliable rate</p>}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </td>
                  );
                })}
              </tr>
            ))}
            {initialSegments.length === 0 && (
              <tr>
                <td colSpan={values.length + 1} className="px-4 py-8 text-center text-gray-500">
                  No data available for this dimension.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
