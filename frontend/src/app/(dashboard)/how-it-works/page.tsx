import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { fetchApi } from '@/lib/api'
import { Database, Filter, BrainCircuit, Activity, Network, Lightbulb, FileText, AlertTriangle, Target } from 'lucide-react'

interface FunnelStats {
  raw: number
  deduped: number
  keyword_pass: number
  llm_relevant: number
  extracted_signals: number
}

interface HowItWorksData {
  funnel: FunnelStats
}

export default async function HowItWorksPage() {
  const data = await fetchApi<HowItWorksData>('/how-it-works')
  const funnel = data?.funnel || {
    raw: 0, deduped: 0, keyword_pass: 0, llm_relevant: 0, extracted_signals: 0
  }

  const pipelineSteps = [
    {
      title: '1. Ingestion',
      icon: <Database className="w-5 h-5 text-blue-500" />,
      description: 'Raw data is continuously collected from Reddit, Hacker News, Google Play, Apple App Store, and the Google Photos Help Community.',
      stat: funnel.raw,
      statLabel: 'Raw Records'
    },
    {
      title: '2. Keyword Prefilter',
      icon: <Filter className="w-5 h-5 text-cyan-500" />,
      description: 'Records are deduped and filtered using a multilingual keyword matrix (English, Hindi, Hinglish) focusing on search, recall, and finding photos.',
      stat: funnel.keyword_pass,
      statLabel: 'Keyword Matches'
    },
    {
      title: '3. Relevance Filter (V3)',
      icon: <BrainCircuit className="w-5 h-5 text-indigo-500" />,
      description: 'An LLM evaluates each record against strict inclusion criteria to separate genuine product friction from feature requests or account issues.',
      stat: funnel.llm_relevant,
      statLabel: 'Relevant Records'
    },
    {
      title: '4. Signal Extraction (V2)',
      icon: <Activity className="w-5 h-5 text-purple-500" />,
      description: 'The LLM extracts structured signals (remembered/forgotten cues, severity, verbatim quotes) and classifies them into funnel stages.',
      stat: funnel.extracted_signals,
      statLabel: 'Extracted Signals'
    },
    {
      title: '5. Embedding & Clustering',
      icon: <Network className="w-5 h-5 text-pink-500" />,
      description: 'Signals are vectorized using FastEmbed and clustered using DBSCAN to mathematically group similar user issues together.',
    },
    {
      title: '6. Theme Synthesis',
      icon: <FileText className="w-5 h-5 text-rose-500" />,
      description: 'Clusters are analyzed to generate human-readable Themes (Core vs Adjacent). Themes are ranked based on frequency, distinct authors, and severity.',
    },
    {
      title: '7. Hypothesis Generation',
      icon: <Lightbulb className="w-5 h-5 text-amber-500" />,
      description: 'For top-ranking themes, the system automatically derives actionable research hypotheses, complete with rationales and recommended research questions.',
    }
  ]

  return (
    <div className="space-y-8 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">How it works</h1>
        <p className="text-muted-foreground mt-2 text-lg">
          Understanding the Listening V2 Pipeline and Research Architecture.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-6">
          <Card>
            <CardHeader className="bg-muted/30">
              <CardTitle className="text-xl flex items-center gap-2">
                <BrainCircuit className="w-6 h-6 text-primary" />
                The Listening V2 Pipeline
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-8 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-border before:to-transparent">
                {pipelineSteps.map((step, index) => (
                  <div key={index} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                    <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-background bg-muted shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
                      {step.icon}
                    </div>
                    <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-lg border bg-card text-card-foreground shadow-sm">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-base">{step.title}</h3>
                        {step.stat !== undefined && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                            {step.stat.toLocaleString()} {step.statLabel}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">{step.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Target className="w-5 h-5 text-emerald-500" />
                Accuracy & Methodologies
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>
                <strong>Zero-Shot Classification:</strong> The extraction phase utilizes strict zero-shot prompting techniques to prevent hallucination. If a signal does not explicitly contain a missing photo intent, it is conservatively rejected.
              </p>
              <p>
                <strong>Multilingual Support:</strong> The ingestion prefilters explicitly capture Hinglish and Devanagari keyword variants (e.g., &quot;photo nahi mil rahi&quot;) to capture context from the IN market.
              </p>
              <p>
                <strong>DBSCAN Density Clustering:</strong> We use epsilon bounds of 0.35 and minimum cluster sizes of 3. This ensures that only mathematically similar complaints are merged into Themes, preventing semantic drift.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                Known Limitations
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong>Sampling Bias:</strong> Data is heavily skewed towards Reddit and Help Communities, which typically represent high-friction "power users" rather than the mainstream user base.
                </li>
                <li>
                  <strong>Temporal Lags:</strong> The pipeline operates on a rolling 24-month window, meaning sudden changes introduced in the latest app update may take time to emerge as top-ranking themes.
                </li>
                <li>
                  <strong>Silent Failures:</strong> Users who experience recall failure but do not post about it online (the vast majority) are entirely absent from this dataset.
                </li>
                <li>
                  <strong>Semantic Overlap:</strong> Highly nuanced issues (e.g., differentiating between "faces not grouping" vs "faces grouped wrong") may occasionally cluster into the same broad theme.
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
