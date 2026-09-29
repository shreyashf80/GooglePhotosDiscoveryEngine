'use client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileDown } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function HandoffClient({ hypotheses }: { hypotheses: any[] }) {
  const downloadMarkdown = () => {
    let md = '# Research Handoff: Data-Derived Hypotheses\n\n';

    hypotheses?.forEach((h: any, i: number) => {
      md += `## ${i + 1}. ${h.title}\n`;
      md += `**Statement:** ${h.statement}\n\n`;
      md += `**Research Question:** ${h.research_question || 'N/A'}\n\n`;
      md += `**Evidence Strength:** ${h.evidence_strength || 'N/A'}\n\n`;
      md += `### Why We Believe It\n${h.details?.why || 'N/A'}\n\n`;
      md += `### Counter-Evidence\n${h.details?.counter || 'None identified'}\n\n`;
      md += `### What Would Disprove It\n${h.details?.disprove || 'N/A'}\n\n`;
      md += `---\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'research_handoff.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center bg-gray-50 p-4 border border-blue-100 rounded-lg">
        <h2 className="text-xl font-semibold text-blue-900">Ranked Research Hypotheses</h2>
        <Button variant="outline" size="sm" onClick={downloadMarkdown}>
          <FileDown className="h-4 w-4 mr-2" /> Export Briefing (Markdown)
        </Button>
      </div>

      <div className="space-y-6">
        {!hypotheses || hypotheses.length === 0 ? (
          <div className="p-8 text-center bg-gray-50 border border-dashed rounded-md text-gray-500">
            No data-derived hypotheses found.
          </div>
        ) : (
          hypotheses.map((h: any, i: number) => (
            <Card key={h.hypothesis_id || i}>
              <CardHeader className="flex flex-row items-start justify-between bg-gray-50/50 border-b pb-4">
                <div className="space-y-1 pr-4">
                  <div className="flex items-center gap-3">
                    <span className="text-xl font-bold text-gray-400">#{i + 1}</span>
                    <CardTitle className="text-lg">{h.title}</CardTitle>
                  </div>
                  <p className="text-sm font-medium text-gray-700 italic border-l-2 border-blue-400 pl-3 ml-8">
                    {h.statement}
                  </p>
                </div>
                {h.evidence_strength && (
                  <Badge variant={h.evidence_strength === 'strong' ? 'default' : 'secondary'} className="capitalize shrink-0">
                    {h.evidence_strength} Evidence
                  </Badge>
                )}
              </CardHeader>
              <CardContent className="p-0">
                <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x">
                  <div className="p-6 space-y-4">
                    <div>
                      <h4 className="font-semibold text-green-700 mb-1 flex items-center gap-1.5">
                        <span className="text-lg leading-none">•</span> Why We Believe It
                      </h4>
                      <p className="text-gray-700 text-sm leading-relaxed">{h.details?.why || 'N/A'}</p>
                    </div>
                    <div>
                      <h4 className="font-semibold text-amber-700 mb-1 flex items-center gap-1.5">
                        <span className="text-lg leading-none">•</span> Counter-Evidence
                      </h4>
                      <p className="text-gray-700 text-sm leading-relaxed">{h.details?.counter || 'None identified'}</p>
                    </div>
                    <div>
                      <h4 className="font-semibold text-red-700 mb-1 flex items-center gap-1.5">
                        <span className="text-lg leading-none">•</span> What Would Disprove It
                      </h4>
                      <p className="text-gray-700 text-sm leading-relaxed">{h.details?.disprove || 'N/A'}</p>
                    </div>
                  </div>
                  <div className="p-6 bg-blue-50/30 flex flex-col">
                    <h4 className="font-semibold text-blue-800 mb-3 flex items-center gap-2">
                      Recommended Research Question
                    </h4>
                    <div className="bg-white p-4 rounded-md border border-blue-100 shadow-sm text-blue-900 font-medium text-sm flex-1 whitespace-pre-wrap">
                      {h.research_question || 'N/A'}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
