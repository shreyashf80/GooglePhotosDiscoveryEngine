import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

export const labelMap: Record<string, string> = {
  // statuses
  "supported": "Supported",
  "contradicted": "Contradicted",
  "mixed": "Mixed Evidence",
  "insufficient_data": "Insufficient Data",
  // stages
  "express": "Express Intent",
  "execute": "Execute Query",
  "refine": "Refine Results",
  "eval_retrieved": "Evaluate Retrieved",
  // archetypes
  "utility": "Utility",
  "memory": "Memory",
  // searchable badges
  "yes": "Searchable",
  "partial": "Partially Searchable",
  "no": "Not Searchable",
  "not_verified": "Not Verified",
  // evidence strength
  "strong": "Strong",
  "moderate": "Moderate",
  "anecdotal": "Anecdotal",
  "none": "None"
}

export function EnumLabel({ value, className, customTooltip }: { value: string, className?: string, customTooltip?: React.ReactNode }) {
  if (!value) return null
  const readable = labelMap[value] || value.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          <span className={`cursor-help ${className || ''}`}>{readable}</span>
        </TooltipTrigger>
        <TooltipContent>
          {customTooltip || <p className="text-xs">Raw value: {value}</p>}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
