'use client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EnumLabel } from '@/components/EnumLabel';
import { Copy, FileDown } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function HandoffClient({ handoff }: { handoff: any }) {
  const { decisions, drafts } = handoff;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const downloadMarkdown = () => {
    let md = '# Research Handoff\n\n## Decisions\n';
    md += `- D1 (Hypotheses to validate): ${decisions.D1.map((h: any) => h.hypothesis_id).join(', ') || 'None'}\n`;
    md += `- D2 (Segments to recruit): ${decisions.D2}\n`;
    md += `- D3 (Archetype deep dive): ${decisions.D3}\n`;
    md += `- D4 (Kill list): ${decisions.D4}\n\n`;

    drafts.forEach((d: any) => {
      md += `## Hypothesis: ${d.hypothesis_id}\n\n### Interview Questions\n${JSON.stringify(d.interview_questions, null, 2)}\n\n### Task Ideas\n${JSON.stringify(d.task_ideas, null, 2)}\n\n### Screener\n${JSON.stringify(d.screener, null, 2)}\n\n`;
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
      <Card className="bg-gray-50 border-blue-100">
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="text-xl text-blue-900">Decision Summary</CardTitle>
            <Button variant="outline" size="sm" onClick={downloadMarkdown}>
              <FileDown className="h-4 w-4 mr-2" /> Export All (Markdown)
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-gray-800">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 className="font-semibold text-blue-800 mb-1">D1: Hypotheses to validate</h4>
              {decisions.D1.length > 0 ? (
                <ul className="list-disc pl-5">
                  {decisions.D1.map((h: any) => (
                    <li key={h.hypothesis_id} className="font-medium">{h.hypothesis_id}: {h.title}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-gray-500">None met the evidence threshold.</p>
              )}
            </div>
            <div>
              <h4 className="font-semibold text-blue-800 mb-1">D2: Segments to recruit</h4>
              <p>{decisions.D2}</p>
            </div>
            <div>
              <h4 className="font-semibold text-blue-800 mb-1">D3: Archetype deep dive</h4>
              <p className="font-medium capitalize">{decisions.D3.replace(/_/g, ' ')}</p>
            </div>
            <div>
              <h4 className="font-semibold text-blue-800 mb-1">D4: Kill list</h4>
              <p>{decisions.D4}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <h3 className="text-xl font-bold border-b pb-2">AI-Drafted Research Assets</h3>
        
        {(!drafts || drafts.length === 0) && (
          <div className="p-8 text-center bg-gray-50 border border-dashed rounded-md text-gray-500">
            Not generated yet. Run the <code className="bg-white px-1 border rounded">handoff</code> command in the pipeline to generate assets.
          </div>
        )}

        {drafts?.map((draft: any) => {
          const stringifyList = (item: any) => {
            if (Array.isArray(item)) return item.map((x: string) => `• ${x}`).join('\n');
            if (typeof item === 'object') return Object.entries(item).map(([k, v]) => `${k}: ${v}`).join('\n');
            return String(item);
          };

          return (
            <Card key={draft.hypothesis_id}>
              <CardHeader className="flex flex-row items-center justify-between bg-gray-50 border-b pb-4">
                <CardTitle className="text-lg flex items-center gap-3">
                  {draft.hypothesis_id} Assets
                  <Badge variant="secondary" className="bg-blue-100 text-blue-800">AI Draft</Badge>
                </CardTitle>
                <div className="text-xs text-gray-400">Generated: {new Date(draft.generated_at).toLocaleString()} using {draft.model_id}</div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x">
                  <div className="p-6 space-y-3 relative group">
                    <div className="flex justify-between items-center">
                      <h4 className="font-semibold text-gray-800">Interview Questions</h4>
                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => copyToClipboard(stringifyList(draft.interview_questions))}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="text-sm whitespace-pre-wrap text-gray-600 font-mono bg-gray-50 p-3 rounded">
                      {stringifyList(draft.interview_questions)}
                    </div>
                  </div>
                  <div className="p-6 space-y-3 relative group">
                    <div className="flex justify-between items-center">
                      <h4 className="font-semibold text-gray-800">Task Ideas</h4>
                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => copyToClipboard(stringifyList(draft.task_ideas))}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="text-sm whitespace-pre-wrap text-gray-600 font-mono bg-gray-50 p-3 rounded">
                      {stringifyList(draft.task_ideas)}
                    </div>
                  </div>
                  <div className="p-6 space-y-3 relative group">
                    <div className="flex justify-between items-center">
                      <h4 className="font-semibold text-gray-800">Screener Criteria</h4>
                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => copyToClipboard(stringifyList(draft.screener))}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="text-sm whitespace-pre-wrap text-gray-600 font-mono bg-gray-50 p-3 rounded">
                      {stringifyList(draft.screener)}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  )
}
