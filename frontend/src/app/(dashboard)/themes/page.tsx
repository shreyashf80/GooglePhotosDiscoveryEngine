import { fetchApi } from '@/lib/api'
import ThemesClient from './client'
import { Suspense } from 'react'

export const revalidate = 60;

async function ThemesData() {
  const themes = await fetchApi<any[]>('/themes', { cache: 'no-store' })
  return <ThemesClient themes={themes || []} />
}

export default function ThemesPage() {
  return (
    <Suspense fallback={<div className="animate-pulse">Loading themes...</div>}>
      <ThemesData />
    </Suspense>
  )
}
