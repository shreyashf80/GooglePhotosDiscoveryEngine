'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { MessageSquare, Users, Network, Quote, ChevronDown, ChevronUp, AlertTriangle, ArrowRight } from 'lucide-react'
import Link from 'next/link'

type Theme = {
  id: string
  scope: string
  name: string
  description: string
  signals: number
  distinct_authors: number
  sources_count: number
  severe_share: number
  rank_score: number
  evidence_strength: string
  mixes?: { funnel?: Record<string, number> }
  quotes?: string[]
}

function ThemeCard({ theme }: { theme: Theme }) {
  const [quotesExpanded, setQuotesExpanded] = useState(false)

  // Primary funnel stage
  let primaryFunnel = 'Unknown'
  if (theme.mixes?.funnel) {
    const funnelEntries = Object.entries(theme.mixes.funnel)
    if (funnelEntries.length > 0) {
      primaryFunnel = funnelEntries.sort((a, b) => b[1] - a[1])[0][0]
    }
  }

  // Evidence badge color
  const evidenceColor = 
    theme.evidence_strength === 'strong' ? 'bg-green-100 text-green-800' :
    theme.evidence_strength === 'moderate' || theme.evidence_strength === 'directional' ? 'bg-blue-100 text-blue-800' :
    'bg-gray-100 text-gray-800'

  // Severity percentage
  const severeSharePercent = theme.severe_share ? Math.round(theme.severe_share * 100) : 0

  return (
    <Card className="flex flex-col h-full overflow-hidden">
      <CardHeader className="pb-3 border-b bg-gray-50/50">
        <div className="flex justify-between items-start gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant={theme.scope === 'core' ? 'default' : 'secondary'} className="uppercase text-[10px] tracking-wider">
                {theme.scope}
              </Badge>
              <Badge variant="outline" className={evidenceColor}>
                {theme.evidence_strength || 'Unknown'} Evidence
              </Badge>
            </div>
            <CardTitle className="text-xl leading-tight">
              {theme.name}
            </CardTitle>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-3xl font-bold text-gray-900">{Math.round(theme.rank_score || 0)}</span>
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Rank Score</span>
          </div>
        </div>
        {theme.description && (
          <p className="text-sm text-gray-600 mt-2 line-clamp-2">{theme.description}</p>
        )}
      </CardHeader>
      
      <CardContent className="pt-4 flex-grow flex flex-col gap-5">
        <div className="grid grid-cols-3 gap-2">
          <div className="flex flex-col gap-1 p-2 bg-gray-50 rounded-md">
            <span className="text-xs text-gray-500 flex items-center gap-1"><MessageSquare className="w-3 h-3" /> Signals</span>
            <span className="font-semibold text-gray-900">{theme.signals || 0}</span>
          </div>
          <div className="flex flex-col gap-1 p-2 bg-gray-50 rounded-md">
            <span className="text-xs text-gray-500 flex items-center gap-1"><Users className="w-3 h-3" /> Authors</span>
            <span className="font-semibold text-gray-900">{theme.distinct_authors || 0}</span>
          </div>
          <div className="flex flex-col gap-1 p-2 bg-gray-50 rounded-md">
            <span className="text-xs text-gray-500 flex items-center gap-1"><Network className="w-3 h-3" /> Sources</span>
            <span className="font-semibold text-gray-900">{theme.sources_count || 0}</span>
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-500 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Severe Complaint Share</span>
            <span className="font-medium">{severeSharePercent}%</span>
          </div>
          <Progress value={severeSharePercent} className="h-1.5" />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Primary Stage:</span>
          <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200 capitalize">
            {primaryFunnel.replace(/_/g, ' ')}
          </Badge>
        </div>

        {theme.quotes && theme.quotes.length > 0 && (
          <div className="mt-auto border rounded-md">
            <button 
              className="w-full flex items-center justify-between p-2 text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 transition-colors"
              onClick={() => setQuotesExpanded(!quotesExpanded)}
            >
              <span className="flex items-center gap-1.5"><Quote className="w-3 h-3" /> Illustrative Quotes ({theme.quotes.length})</span>
              {quotesExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            
            {quotesExpanded && (
              <div className="p-3 space-y-3 bg-white border-t">
                {theme.quotes.slice(0, 3).map((quote, idx) => (
                  <div key={idx} className="text-sm italic text-gray-700 border-l-2 border-gray-300 pl-3">
                    "{quote}"
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <Link href={`/evidence-browser?theme=${theme.id}`} className="mt-2 w-full flex items-center justify-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline">
          View Evidence <ArrowRight className="w-4 h-4" />
        </Link>
      </CardContent>
    </Card>
  )
}

export default function ThemesClient({ themes }: { themes: Theme[] }) {
  const coreThemes = themes.filter(t => t.scope === 'core')
  const adjacentThemes = themes.filter(t => t.scope === 'adjacent')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Themes</h1>
        <p className="text-sm text-gray-500 mt-1">Data-derived problem clusters based on semantic similarity of signals.</p>
      </div>

      <Tabs defaultValue="core" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="core">Core Themes ({coreThemes.length})</TabsTrigger>
          <TabsTrigger value="adjacent">Adjacent Themes ({adjacentThemes.length})</TabsTrigger>
        </TabsList>
        
        <TabsContent value="core" className="space-y-4">
          {coreThemes.length === 0 ? (
            <div className="text-center p-8 bg-gray-50 rounded-lg text-gray-500 border border-dashed">
              No core themes identified yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {coreThemes.map(theme => (
                <ThemeCard key={theme.id} theme={theme} />
              ))}
            </div>
          )}
        </TabsContent>
        
        <TabsContent value="adjacent" className="space-y-4">
          {adjacentThemes.length === 0 ? (
            <div className="text-center p-8 bg-gray-50 rounded-lg text-gray-500 border border-dashed">
              Not enough adjacent signals to form themes yet. Minimum 5 distinct authors required.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {adjacentThemes.map(theme => (
                <ThemeCard key={theme.id} theme={theme} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
