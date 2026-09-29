import { fetchApi } from '@/lib/api'
import ThemesClient from './client'
import { Suspense } from 'react'

async function ThemesData() {
  const themes = await fetchApi<any[]>('/themes')
  return <ThemesClient themes={themes || []} />
}

export default function ThemesPage() {
  return (
    <Suspense fallback={<div className="animate-pulse">Loading themes...</div>}>
      <ThemesData />
    </Suspense>
  )
}
