import Link from 'next/link'
import { ReactNode } from 'react'

const navItems = [
  { name: 'Overview', href: '/' },
  { name: 'Hypothesis board', href: '/hypothesis-board' },
  { name: 'Gap matrix', href: '/gap-matrix' },
  { name: 'Archetype explorer', href: '/archetype-explorer' },
  { name: 'Segment explorer', href: '/segment-explorer', p1: true },
  { name: 'Evidence browser', href: '/evidence-browser' },
  { name: 'Ask the corpus', href: '/ask' },
  { name: 'Research handoff', href: '/research-handoff', p1: true },
  { name: 'How it works', href: '/how-it-works' },
]

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <nav className="w-64 bg-white border-r flex-shrink-0">
        <div className="h-16 flex items-center px-6 border-b">
          <h1 className="text-xl font-bold">Recall Gap</h1>
        </div>
        <div className="p-4 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            >
              {item.name}
              {item.p1 && (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                  P1
                </span>
              )}
            </Link>
          ))}
        </div>
      </nav>
      <main className="flex-1 overflow-y-auto p-8">
        {children}
      </main>
    </div>
  )
}
