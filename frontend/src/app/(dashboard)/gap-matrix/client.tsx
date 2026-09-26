'use client'

import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EnumLabel } from '@/components/EnumLabel'

export default function GapMatrixClient({ data }: { data: any[] }) {
  const [sortCol, setSortCol] = useState<string>('gap_score')
  const [sortDesc, setSortDesc] = useState<boolean>(true)

  const handleSort = (col: string) => {
    if (sortCol === col) setSortDesc(!sortDesc)
    else {
      setSortCol(col)
      setSortDesc(true)
    }
  }

  const sortedData = [...data].sort((a, b) => {
    let valA = a[sortCol]
    let valB = b[sortCol]
    if (valA == null) valA = -1
    if (valB == null) valB = -1
    if (valA < valB) return sortDesc ? 1 : -1
    if (valA > valB) return sortDesc ? -1 : 1
    return 0
  })

  const topGaps = [...data].filter(d => d.gap_score != null).sort((a, b) => b.gap_score - a.gap_score).slice(0, 5)
  const forgottenData = [...data].sort((a, b) => (b.forgotten_count || 0) - (a.forgotten_count || 0))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Gap Matrix</h1>
        <p className="text-sm text-gray-500 mt-1">Comparing user recall against search system capability across cue types.</p>
      </div>
      
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <h3 className="text-sm font-semibold text-blue-900 mb-2 uppercase tracking-wider">Top 5 Gaps (Remembered but not searchable)</h3>
          <div className="flex flex-wrap gap-2">
            {topGaps.map((g, i) => (
              <span key={g.cue_type} className="px-3 py-1 bg-white border border-blue-200 rounded-full text-sm font-medium text-blue-800 flex items-center">
                {i + 1}. <EnumLabel value={g.cue_type} className="ml-1" /> <span className="text-blue-400 ml-1">gap score {(g.gap_score * 100).toFixed(1)}</span>
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="matrix">
        <TabsList>
          <TabsTrigger value="matrix">Gap Matrix</TabsTrigger>
          <TabsTrigger value="forgotten">Forgotten Cues</TabsTrigger>
        </TabsList>
        <TabsContent value="matrix" className="pt-4">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader className="bg-gray-50">
                  <TableRow>
                    <TableHead className="cursor-pointer hover:bg-gray-100" onClick={() => handleSort('cue_type')}>Cue Type</TableHead>
                    <TableHead className="cursor-pointer hover:bg-gray-100" onClick={() => handleSort('remembered_share')}>Remembered %</TableHead>
                    <TableHead>
                      Precision 
                      <span className="text-xs font-normal ml-2 text-gray-500">
                        (<span className="inline-block w-2 h-2 bg-green-500 rounded-full mx-1"></span>Exact 
                        <span className="inline-block w-2 h-2 bg-yellow-500 rounded-full mx-1 ml-2"></span>Approx 
                        <span className="inline-block w-2 h-2 bg-red-500 rounded-full mx-1 ml-2"></span>Vague)
                      </span>
                    </TableHead>
                    <TableHead className="cursor-pointer hover:bg-gray-100" onClick={() => handleSort('failure_rate')}>Failure %</TableHead>
                    <TableHead className="cursor-pointer hover:bg-gray-100" onClick={() => handleSort('searchable')}>Searchable</TableHead>
                    <TableHead className="cursor-pointer hover:bg-gray-100 text-right" onClick={() => handleSort('gap_score')}>Gap Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedData.map(row => (
                    <TableRow key={row.cue_type}>
                      <TableCell className="font-medium"><EnumLabel value={row.cue_type} /></TableCell>
                      <TableCell>{row.remembered_share ? (row.remembered_share * 100).toFixed(1) + '%' : '-'}</TableCell>
                      <TableCell>
                        <div className="flex h-2 w-full bg-gray-100 rounded overflow-hidden mt-2">
                          <div style={{width: `${(row.precision_exact || 0) * 100}%`}} className="bg-green-500" title={`Exact: ${Math.round((row.precision_exact || 0) * 100)}%`} />
                          <div style={{width: `${(row.precision_approximate || 0) * 100}%`}} className="bg-yellow-500" title={`Approximate: ${Math.round((row.precision_approximate || 0) * 100)}%`} />
                          <div style={{width: `${(row.precision_vague || 0) * 100}%`}} className="bg-red-500" title={`Vague: ${Math.round((row.precision_vague || 0) * 100)}%`} />
                        </div>
                      </TableCell>
                      <TableCell>{row.failure_rate ? (row.failure_rate * 100).toFixed(1) + '%' : '-'}</TableCell>
                      <TableCell>
                        {!row.searchable ? (
                          <EnumLabel value="not_verified" className="text-gray-400 text-sm" />
                        ) : (
                          <EnumLabel 
                            value={row.searchable} 
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              row.searchable === 'yes' ? 'bg-green-100 text-green-800' :
                              row.searchable === 'partial' ? 'bg-amber-100 text-amber-800' :
                              'bg-red-100 text-red-800'
                            }`}
                            customTooltip={
                              <>
                                <p className="max-w-xs">{row.note}</p>
                                <p className="text-xs text-gray-500 mt-1 italic">Verified: {row.verified_how}</p>
                              </>
                            }
                          />
                        )}
                      </TableCell>
                      <TableCell className="text-right font-bold">{row.gap_score != null ? (row.gap_score * 100).toFixed(1) : '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="forgotten" className="pt-4">
          <Card>
            <CardHeader><CardTitle>Explicitly Forgotten Cues</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-4">
                {forgottenData.filter(d => d.forgotten_count > 0).map((d, i) => (
                  <div key={d.cue_type} className="flex items-center">
                    <span className="w-8 text-gray-400">{i + 1}.</span>
                    <span className="w-32 font-medium">{d.cue_type}</span>
                    <div className="flex-1 ml-4">
                      <div className="h-4 bg-gray-100 rounded-sm overflow-hidden">
                        <div 
                          className="h-full bg-red-400" 
                          style={{ width: `${Math.min((d.forgotten_count / (forgottenData[0].forgotten_count || 1)) * 100, 100)}%` }} 
                        />
                      </div>
                    </div>
                    <span className="ml-4 font-bold w-12 text-right">{d.forgotten_count}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
