import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, startOfMonth } from 'date-fns'
import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line } from 'recharts'
import { categoriesApi } from '@/lib/hooks'
import { formatCurrency } from '@/lib/format'

const COLORS = ['#4a90d9', '#48bb78', '#fc8181', '#f6ad55', '#9f7aea', '#38b2ac', '#ed8936', '#667eea']

export default function CategoriesPage() {
  const [dateFrom, setDateFrom] = useState(format(startOfMonth(new Date()), 'yyyy-MM-dd'))
  const [dateTo, setDateTo] = useState(format(new Date(), 'yyyy-MM-dd'))

  const { data: breakdown, isLoading } = useQuery({
    queryKey: ['category-breakdown', dateFrom, dateTo],
    queryFn: () => categoriesApi.breakdown({ date_from: dateFrom, date_to: dateTo }),
  })

  const { data: merchants } = useQuery({
    queryKey: ['merchants', dateFrom, dateTo],
    queryFn: () => categoriesApi.merchants({ date_from: dateFrom, date_to: dateTo, limit: 10 }),
  })

  const { data: trends } = useQuery({
    queryKey: ['category-trends'],
    queryFn: () => categoriesApi.trends(6),
  })

  const pieData = (breakdown?.categories || []).map((c) => ({ name: c.category, value: c.total }))

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl m-0">Categories</h1>
          <p className="text-[var(--neu-text-secondary)] mt-1">Spending trends and merchant breakdown</p>
        </div>
        <div className="flex gap-3">
          <input className="neu-input px-3 py-2" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input className="neu-input px-3 py-2" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
      </header>

      {isLoading ? (
        <div className="neu-raised p-8">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="neu-raised p-6">
            <h2 className="text-lg mt-0">Category breakdown</h2>
            <p className="text-sm text-[var(--neu-text-secondary)]">
              Total outflow: {formatCurrency(breakdown?.period_total_outflow || 0)}
            </p>
            <div className="h-64 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" outerRadius={95} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="list-none p-0 mt-4 space-y-2">
              {(breakdown?.categories || []).map((c) => (
                <li key={c.category} className="flex justify-between text-sm">
                  <span>{c.category} ({c.count})</span>
                  <span className="tabular-nums">{formatCurrency(c.total)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="neu-raised p-6">
            <h2 className="text-lg mt-0">Top merchants</h2>
            <ul className="list-none p-0 mt-4 space-y-3">
              {(merchants || []).map((m) => (
                <li key={m.merchant} className="neu-inset-sm p-3 flex justify-between gap-3">
                  <div>
                    <p className="m-0 font-medium">{m.merchant}</p>
                    <p className="m-0 text-xs text-[var(--neu-text-secondary)]">{m.count} transactions</p>
                  </div>
                  <span className="tabular-nums">{formatCurrency(m.total)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <div className="neu-raised p-6">
        <h2 className="text-lg mt-0 mb-4">Month-over-month trends</h2>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {(trends || []).slice(0, 9).map((t) => (
            <div key={t.category} className="neu-inset-sm p-3">
              <p className="text-sm font-medium m-0 mb-2">{t.category}</p>
              <div className="h-20">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={t.points}>
                    <Line type="monotone" dataKey="total" stroke="var(--neu-accent)" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
