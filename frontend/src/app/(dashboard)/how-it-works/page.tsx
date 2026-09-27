import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { EnumLabel } from '@/components/EnumLabel'
import { fetchApi } from '@/lib/api'

export default async function HowItWorksPage() {
  const literature = await fetchApi<any[]>('/literature')
  
  // Group by era
  const grouped: Record<string, any[]> = {}
  if (Array.isArray(literature)) {
    literature.forEach(src => {
      const era = src.era || 'unknown'
      if (!grouped[era]) grouped[era] = []
      grouped[era].push(src)
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">How it works</h1>
        <p className="text-sm text-gray-500 mt-1">Understanding the discovery engine and research foundation.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Evidence Base</CardTitle>
        </CardHeader>
        <CardContent>
          {Object.entries(grouped).map(([era, sources]) => (
            <div key={era} className="mb-6 last:mb-0">
              <h3 className="text-lg font-semibold capitalize mb-3 pb-1 border-b flex items-center gap-2">
                <EnumLabel value={era} /> Era
              </h3>
              <div className="space-y-4">
                {sources.map(src => (
                  <div key={src.id} className="p-4 border rounded bg-gray-50 flex flex-col gap-2">
                    <div className="flex justify-between">
                      <h4 className="font-semibold">{src.title}</h4>
                      <div className="flex gap-1 flex-wrap justify-end max-w-xs">
                        {src.tags?.map((t: string) => (
                          <span key={t} className="px-2 py-0.5 bg-gray-200 text-gray-800 text-xs rounded-full">{t}</span>
                        ))}
                      </div>
                    </div>
                    <p className="text-sm text-gray-700">{src.citation}</p>
                    {src.link && (
                      <a href={src.link} target="_blank" rel="noreferrer" className="text-blue-600 text-sm hover:underline w-fit">
                        View Source &rarr;
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {Object.keys(grouped).length === 0 && <p className="text-sm text-gray-500">No evidence base loaded.</p>}
        </CardContent>
      </Card>
    </div>
  )
}
