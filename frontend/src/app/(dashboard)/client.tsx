'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer,
  ComposedChart, Line
} from 'recharts'

export function PipelineFunnelChart({ data }: { data: any[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>Pipeline Funnel</CardTitle></CardHeader>
      <CardContent className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 40, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="name" type="category" width={80} />
            <RechartsTooltip />
            <Bar dataKey="value" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function RetrievalFunnelChart({ data }: { data: any[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>Retrieval Funnel Failures</CardTitle></CardHeader>
      <CardContent className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" tickFormatter={(v) => `${v}%`} />
            <RechartsTooltip />
            <Legend />
            <Bar yAxisId="left" dataKey="Episodes" stackId="a" fill="#8b5cf6" />
            <Bar yAxisId="left" dataKey="Complaints" stackId="a" fill="#c4b5fd" />
            <Line yAxisId="right" type="monotone" dataKey="GaveUpRate" name="Gave Up %" stroke="#ef4444" strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
