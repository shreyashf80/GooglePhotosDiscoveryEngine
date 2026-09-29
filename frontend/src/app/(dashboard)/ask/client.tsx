'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, MessageSquareText, Loader2, BookOpen, ExternalLink, FileText, GraduationCap, Sparkles, Info } from 'lucide-react';

interface Citation {
  id: string;
  signal_id: string;
  quote_en: string;
  quote_original?: string;
  source: string;
  url: string;
  date: string;
}

interface LiteratureCitation {
  id: string;
  title: string;
  era: string;
  link: string;
}

interface ChatResponse {
  answer: string;
  citations: Citation[];
  literature_citations: LiteratureCitation[];
  rewritten_query: string;
  stats_used: boolean;
  cached: boolean;
  insufficient_evidence: boolean;
  error?: string;
}

const STARTER_QUESTIONS = [
  'What cues do users remember about screenshots they are searching for?',
  'What are the most common reasons users fail to find their photos?',
  'How do users react when AI search blocks their safe search terms?',
  'What workarounds do users try when the search engine fails them?',
];

function renderAnswerWithCitations(
  answer: string,
  onCitationClick: (id: string) => void
) {
  // Split on citation markers [E1], [R2], etc.
  const parts = answer.split(/(\[[ER]\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[([ER])(\d+)\]$/);
    if (match) {
      const type = match[1];
      const isEpisode = type === 'E';
      return (
        <button
          key={i}
          onClick={() => onCitationClick(part.slice(1, -1))}
          className={`inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-xs font-semibold cursor-pointer transition-all duration-150 ${
            isEpisode
              ? 'bg-blue-100 text-blue-700 hover:bg-blue-200 border border-blue-200'
              : 'bg-purple-100 text-purple-700 hover:bg-purple-200 border border-purple-200'
          }`}
          title={`Click to view ${isEpisode ? 'signal' : 'research'} details`}
        >
          {part}
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function AskClient() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightedCitation, setHighlightedCitation] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const answerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (q?: string) => {
    const finalQuestion = q || question;
    if (!finalQuestion.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResponse(null);
    setHighlightedCitation(null);
    setQuestion(finalQuestion);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: finalQuestion }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || `Error ${res.status}`);
        return;
      }

      if (data.error) {
        setError(data.error);
        return;
      }

      setResponse(data);
    } catch (err) {
      setError('Failed to connect to the server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCitationClick = (citationId: string) => {
    setHighlightedCitation(citationId);

    // If it's an episode citation, try to find it and we could scroll to it
    if (citationId.startsWith('E') && response) {
      const idx = parseInt(citationId.slice(1)) - 1;
      const citation = response.citations[idx];
      if (citation) {
        // Scroll the side panel to highlight the citation
        const el = document.getElementById(`citation-${citationId}`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } else if (citationId.startsWith('R') && response) {
      const el = document.getElementById(`citation-${citationId}`);
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const handleSignalOpen = (signalId: string) => {
    window.open(`/evidence-browser?search=${encodeURIComponent(signalId)}`, '_blank');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const hasResults = response && !error;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <MessageSquareText className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-gray-900">Ask the Corpus</h1>
            <p className="text-sm text-gray-500">Ask questions about user photo retrieval experiences</p>
          </div>
        </div>
      </div>

      {/* Main content area */}
      <div className="flex-1 min-h-0 flex flex-col">
        {/* Input + starter questions (shown at top) */}
        <div className="flex-shrink-0">
          <div className="relative bg-white rounded-xl border shadow-sm">
            <textarea
              ref={inputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about the collected evidence..."
              rows={2}
              disabled={loading}
              className="w-full px-4 py-3 pr-12 rounded-xl border-0 focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none text-sm disabled:opacity-50 disabled:bg-gray-50"
            />
            <button
              onClick={() => handleSubmit()}
              disabled={!question.trim() || loading}
              className="absolute right-3 bottom-3 p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 transition-colors"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>

          {/* Starter questions */}
          {!hasResults && !loading && (
            <div className="mt-4 grid grid-cols-2 gap-2">
              {STARTER_QUESTIONS.map((sq) => (
                <button
                  key={sq}
                  onClick={() => handleSubmit(sq)}
                  className="group text-left p-3 rounded-lg border bg-white hover:bg-blue-50 hover:border-blue-200 transition-all duration-150 text-sm text-gray-700 hover:text-blue-700"
                >
                  <div className="flex items-start gap-2">
                    <Sparkles className="h-4 w-4 mt-0.5 text-gray-400 group-hover:text-blue-500 flex-shrink-0 transition-colors" />
                    <span>{sq}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-3">
              <div className="relative mx-auto w-12 h-12">
                <div className="absolute inset-0 rounded-full border-4 border-blue-100"></div>
                <div className="absolute inset-0 rounded-full border-4 border-blue-500 border-t-transparent animate-spin"></div>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">Searching the corpus...</p>
                <p className="text-xs text-gray-500 mt-1">Rewriting query → Embedding → Retrieving signals → Generating answer</p>
              </div>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="mt-4 p-4 rounded-lg bg-red-50 border border-red-200">
            <p className="text-sm text-red-700 font-medium">Error</p>
            <p className="text-sm text-red-600 mt-1">{error}</p>
          </div>
        )}

        {/* Results */}
        {hasResults && (
          <div className="mt-4 flex-1 min-h-0 grid grid-cols-3 gap-4" style={{ maxHeight: 'calc(100vh - 320px)' }}>
            {/* Answer panel (2/3) */}
            <div className="col-span-2 flex flex-col min-h-0">
              {/* Rewritten query badge */}
              <div className="flex-shrink-0 flex items-center gap-2 mb-3">
                <span className="text-xs font-medium text-gray-500">Searched for:</span>
                <span className="text-xs px-2 py-1 bg-gray-100 rounded-full text-gray-700 font-mono">
                  {response.rewritten_query}
                </span>
                {response.cached && (
                  <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                    cached
                  </span>
                )}
              </div>

              {/* Insufficient evidence warning */}
              {response.insufficient_evidence && (
                <div className="flex-shrink-0 mb-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                  <div className="flex items-center gap-2">
                    <Info className="h-4 w-4 text-amber-600 flex-shrink-0" />
                    <p className="text-sm text-amber-700">
                      <span className="font-medium">Limited evidence:</span> Fewer than 3 relevant signals were found. Research findings are shown where available.
                    </p>
                  </div>
                </div>
              )}

              {/* Answer text */}
              <div ref={answerRef} className="flex-1 overflow-y-auto bg-white rounded-xl border p-5 shadow-sm">
                <div className="prose prose-sm max-w-none text-gray-800 leading-relaxed">
                  {response.answer.split('\n').map((paragraph, i) => {
                    if (!paragraph.trim()) return <br key={i} />;
                    return (
                      <p key={i} className="mb-3">
                        {renderAnswerWithCitations(paragraph, handleCitationClick)}
                      </p>
                    );
                  })}
                </div>
              </div>

              {/* Disclaimer */}
              <div className="flex-shrink-0 mt-3 flex items-start gap-2 px-1">
                <Info className="h-3.5 w-3.5 text-gray-400 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-gray-500 leading-relaxed">
                  Answers use only collected public posts and curated research. Counts come from precomputed stats.
                </p>
              </div>
            </div>

            {/* Citations side panel (1/3) */}
            <div className="flex flex-col min-h-0">
              <div className="flex-1 overflow-y-auto space-y-3">
                {/* Episode citations */}
                {response.citations.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <FileText className="h-4 w-4 text-blue-600" />
                      <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                        User Evidence ({response.citations.length})
                      </h3>
                    </div>
                    <div className="space-y-2">
                      {response.citations.map((cit) => (
                        <div
                          key={cit.id}
                          id={`citation-${cit.id}`}
                          className={`p-3 rounded-lg border text-sm transition-all duration-200 cursor-pointer hover:shadow-md ${
                            highlightedCitation === cit.id
                              ? 'bg-blue-50 border-blue-300 shadow-sm ring-1 ring-blue-200'
                              : 'bg-white border-gray-200 hover:border-blue-200'
                          }`}
                          onClick={() => handleSignalOpen(cit.signal_id)}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-700">
                              [{cit.id}]
                            </span>
                            <div className="flex items-center gap-1.5 text-xs text-gray-500">
                              <span className="capitalize">{cit.source}</span>
                              {cit.date && <span>· {cit.date}</span>}
                            </div>
                          </div>
                          <p className="text-gray-700 text-xs leading-relaxed italic line-clamp-3">
                            &ldquo;{cit.quote_en}&rdquo;
                          </p>
                          {cit.quote_original && (
                            <p className="text-gray-500 text-xs mt-1 italic line-clamp-2">
                              Original: &ldquo;{cit.quote_original}&rdquo;
                            </p>
                          )}
                          {cit.url && (
                            <div className="mt-1.5 flex items-center gap-1 text-xs text-blue-600 hover:underline">
                              <ExternalLink className="h-3 w-3" />
                              <span>View in Evidence Browser</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Literature citations */}
                {response.literature_citations.length > 0 && (
                  <div className={response.citations.length > 0 ? 'mt-4' : ''}>
                    <div className="flex items-center gap-2 mb-2">
                      <GraduationCap className="h-4 w-4 text-purple-600" />
                      <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                        Research ({response.literature_citations.length})
                      </h3>
                    </div>
                    <div className="space-y-2">
                      {response.literature_citations.map((lit) => (
                        <div
                          key={lit.id}
                          id={`citation-${lit.id}`}
                          className={`p-3 rounded-lg border text-sm transition-all duration-200 ${
                            highlightedCitation === lit.id
                              ? 'bg-purple-50 border-purple-300 shadow-sm ring-1 ring-purple-200'
                              : 'bg-white border-gray-200 hover:border-purple-200'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold bg-purple-100 text-purple-700">
                              [{lit.id}]
                            </span>
                            {lit.era && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 border border-purple-200">
                                {lit.era}
                              </span>
                            )}
                          </div>
                          <p className="text-gray-700 text-xs font-medium leading-relaxed">
                            {lit.title}
                          </p>
                          {lit.link && (
                            <a
                              href={lit.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-1.5 flex items-center gap-1 text-xs text-purple-600 hover:underline"
                            >
                              <ExternalLink className="h-3 w-3" />
                              <span>View paper</span>
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* No citations */}
                {response.citations.length === 0 && response.literature_citations.length === 0 && (
                  <div className="p-4 text-center text-sm text-gray-500 bg-gray-50 rounded-lg border border-dashed border-gray-200">
                    <BookOpen className="h-5 w-5 mx-auto mb-2 text-gray-400" />
                    <p>No citations in this answer</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
