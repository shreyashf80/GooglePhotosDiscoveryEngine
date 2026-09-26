import Link from 'next/link'
import { Badge } from '@/components/ui/badge'

export function EvidenceBadge({ strength }: { strength: string }) {
  const variantMap: Record<string, 'default' | 'secondary' | 'outline'> = {
    strong: 'default',
    directional: 'secondary',
    anecdotal: 'outline',
  }
  const colorMap: Record<string, string> = {
    strong: 'bg-green-100 text-green-800 border-green-200',
    directional: 'bg-blue-100 text-blue-800 border-blue-200',
    anecdotal: 'bg-gray-100 text-gray-800 border-gray-200',
  }
  return (
    <Badge variant="outline" className={`${colorMap[strength] || colorMap.anecdotal}`}>
      {strength}
    </Badge>
  )
}

export function ClickableCount({ count, param, value }: { count: number, param?: string, value?: string }) {
  if (count === 0) return <span>0</span>
  const href = param && value ? `/evidence-browser?${param}=${encodeURIComponent(value)}` : '/evidence-browser'
  return (
    <Link href={href} className="text-blue-600 hover:underline font-medium">
      {count}
    </Link>
  )
}

export function LoadingState() {
  return <div className="flex h-32 items-center justify-center text-gray-500 animate-pulse">Loading data...</div>
}

export function ErrorState({ error }: { error?: string }) {
  return <div className="p-4 bg-red-50 text-red-600 rounded-md border border-red-200">Error loading data{error ? `: ${error}` : ''}</div>
}

export function EmptyState({ message = 'No data available' }: { message?: string }) {
  return <div className="flex h-32 items-center justify-center text-gray-500 border border-dashed rounded-md bg-gray-50">{message}</div>
}
