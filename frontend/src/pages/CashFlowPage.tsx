import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts'
import { format, startOfMonth } from 'date-fns'
import SegmentedControl from '@/components/SegmentedControl'
import { cashFlowApi } from '@/lib/hooks'
import { formatCurrency } from '@/lib/format'

type Granularity = 'daily' | 'weekly' | 'monthly' | 'yearly'

export default function CashFlowPage() {
  const [granularity, setGranularity] = useState<Granularity>('monthly')
  const [dateFrom, setDateFrom] = useState(format(startOfMonth(new Date()), 'yyyy-MM-dd'))
  const [dateTo, setDateTo] = useState(format(new Date(), 'yyyy-MM-dd'))

  const { data, isLoading } = useQuery({
    queryKey: ['cash-flow', granularity, dateFrom, dateTo],
    queryFn: () => cashFlowApi.get({ granularity, date_from: dateFrom, date_to: dateTo }),
  })

  const chartData = useMemo(
    () =>
      (data?.buckets || []).map((b) => ({
        date: b.date,
        inflow: b.inflow,
        outflow: -b.outflow,
        net: b.net,
        cumulative: b.cumulative_net,
      })),
    [data],
  )

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl m-0">Cash Flow</h1>
          <p className="text-[var(--neu-text-secondary)] mt-1">
            {format(new Date(dateFrom), 'MMM d, yyyy')} – {format(new Date(dateTo), 'MMM d, yyyy')} · transfers excluded
          </p>
        </div>
        <SegmentedControl
          value={granularity}
          onChange={(v) => setGranularity(v as Granularity)}
          options={[
            { value: 'daily', label: 'Daily' },
            { value: 'weekly', label: 'Weekly' },
            { value: 'monthly', label: 'Monthly' },
            { value: 'yearly', label: 'Yearly' },
          ]}
        />
      </header>

      <div className="neu-raised p-4 flex flex-wrap gap-4 items-end">
        <label className="text-sm">
          From
          <input className="neu-input block mt-1 px-3 py-2" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label className="text-sm">
          To
          <input className="neu-input block mt-1 px-3 py-2" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
      </div>

      {isLoading || !data ? (
        <div className="neu-raised p-8">Loading cash flow...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="neu-raised p-5">
              <p className="text-sm text-[var(--neu-text-secondary)] m-0">Inflow (selected period)</p>
              <p className="text-2xl tabular-nums text-[var(--neu-positive)] m-0 mt-2">{formatCurrency(data.summary.total_inflow)}</p>
            </div>
            <div className="neu-raised p-5">
              <p className="text-sm text-[var(--neu-text-secondary)] m-0">Outflow (selected period)</p>
              <p className="text-2xl tabular-nums text-[var(--neu-negative)] m-0 mt-2">{formatCurrency(data.summary.total_outflow)}</p>
            </div>
            <div className="neu-raised p-5">
              <p className="text-sm text-[var(--neu-text-secondary)] m-0">Net</p>
              <p className="text-2xl tabular-nums m-0 mt-2">{formatCurrency(data.summary.net)}</p>
            </div>
          </div>

          <div className="neu-raised p-6">
            <h2 className="text-lg mt-0">Inflow / Outflow</h2>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--neu-border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--neu-text-secondary)', fontSize: 12 }} />
                  <YAxis tick={{ fill: 'var(--neu-text-secondary)', fontSize: 12 }} />
                  <Tooltip formatter={(v) => formatCurrency(Number(v))} />
                  <Legend />
                  <Bar dataKey="inflow" fill="var(--neu-positive)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="outflow" fill="var(--neu-negative)" radius={[0, 0, 4, 4]} />
                  <Line type="monotone" dataKey="net" stroke="var(--neu-accent)" strokeWidth={2} dot={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="neu-raised p-6">
            <h2 className="text-lg mt-0">Cumulative net</h2>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--neu-border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--neu-text-secondary)', fontSize: 12 }} />
                  <YAxis tick={{ fill: 'var(--neu-text-secondary)', fontSize: 12 }} />
                  <Tooltip formatter={(v) => formatCurrency(Number(v))} />
                  <Line type="monotone" dataKey="cumulative" stroke="var(--neu-accent)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
