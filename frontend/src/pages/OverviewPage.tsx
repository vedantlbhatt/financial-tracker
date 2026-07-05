import { format, parseISO } from 'date-fns'
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { overviewApi } from '@/lib/hooks'
import { formatCurrency } from '@/lib/format'

const COLORS = ['#4a90d9', '#48bb78', '#fc8181', '#f6ad55', '#9f7aea', '#38b2ac']

export default function OverviewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['overview'],
    queryFn: overviewApi.get,
  })

  if (isLoading || !data) {
    return <div className="neu-raised p-8">Loading overview...</div>
  }

  const monthLabel = format(new Date(), 'MMMM yyyy')
  const sparkData = data.month_sparkline.map((v, i) => ({ i, v }))
  const donutData = data.top_categories.map((c) => ({ name: c.category, value: c.total }))

  return (
    <div className="space-y-6">
      <header>
        <div>
          <h1 className="text-3xl m-0">Overview</h1>
          <p className="text-[var(--neu-text-secondary)] mt-1">Your financial snapshot for {monthLabel}</p>
          {data.last_sync_at && (
            <p className="text-xs text-[var(--neu-text-secondary)] mt-1 m-0">
              Local data · last bank sync {format(parseISO(data.last_sync_at), 'MMM d, h:mm a')}
              {data.requests_remaining_today != null &&
                ` · ${data.requests_remaining_today}/${data.daily_request_limit ?? 24} SimpleFIN requests left today`}
            </p>
          )}
        </div>
      </header>

      {data.rate_limit_notice && (
        <div className="neu-raised p-4 border-l-4 border-[var(--neu-warning)]">
          <p className="font-medium m-0">SimpleFIN rate limit</p>
          <p className="text-sm text-[var(--neu-text-secondary)] mt-1 m-0">{data.rate_limit_notice}</p>
        </div>
      )}

      {data.account_errors && data.account_errors.length > 0 && (
        <div className="neu-raised p-4 border-l-4 border-[var(--neu-warning)]">
          <p className="font-medium m-0">Bank connection needs attention</p>
          <p className="text-sm text-[var(--neu-text-secondary)] mt-1 m-0">
            Re-link your bank on the SimpleFIN Bridge dashboard, then sync again in Settings.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="neu-raised p-6 xl:col-span-1">
          <p className="text-sm text-[var(--neu-text-secondary)]">Net worth</p>
          <p className="text-4xl font-semibold tabular-nums mt-2">{formatCurrency(data.net_worth)}</p>
        </div>

        <div className="neu-raised p-6 xl:col-span-2">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-sm text-[var(--neu-text-secondary)]">{monthLabel} net cash flow</p>
              <p
                className="text-4xl font-semibold tabular-nums mt-2"
                style={{ color: data.month_net >= 0 ? 'var(--neu-positive)' : 'var(--neu-negative)' }}
              >
                {formatCurrency(data.month_net)}
              </p>
              <p className="text-sm text-[var(--neu-text-secondary)] mt-2">
                In {formatCurrency(data.month_inflow)} · Out {formatCurrency(data.month_outflow)}
              </p>
              <p className="text-xs text-[var(--neu-text-secondary)] mt-1">
                Year to date: In {formatCurrency(data.ytd_inflow)} · Out {formatCurrency(data.ytd_outflow)} · Net{' '}
                {formatCurrency(data.ytd_net)}
              </p>
            </div>
            <div className="w-40 h-16">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sparkData}>
                  <Line type="monotone" dataKey="v" stroke="var(--neu-accent)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>

      <div className="neu-raised p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
          <h2 className="text-lg m-0">Paychecks & income</h2>
          {data.last_sync_at && (
            <p className="text-xs text-[var(--neu-text-secondary)] m-0">
              Last bank sync {format(parseISO(data.last_sync_at), 'MMM d, h:mm a')}
            </p>
          )}
        </div>
        {data.recent_income.length === 0 ? (
          <p className="text-[var(--neu-text-secondary)] text-sm m-0">
            No payroll deposits synced yet. If you see a deposit in Bank of America, hit Sync in Settings — SimpleFIN
            can lag a few hours behind your bank.
          </p>
        ) : (
          <ul className="space-y-3 p-0 list-none m-0">
            {data.recent_income.map((dep) => (
              <li
                key={`${dep.date}-${dep.payee}-${dep.amount}`}
                className="flex flex-wrap items-center justify-between gap-2 neu-inset-sm px-4 py-3"
              >
                <div>
                  <p className="font-medium m-0">{dep.payee}</p>
                  <p className="text-sm text-[var(--neu-text-secondary)] m-0 mt-0.5">
                    {format(parseISO(dep.date), 'MMM d, yyyy')} · {dep.category}
                  </p>
                </div>
                <p className="text-xl tabular-nums m-0 text-[var(--neu-positive)]">{formatCurrency(dep.amount)}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="neu-raised p-6 lg:col-span-2">
          <h2 className="text-lg mt-0 mb-4">Accounts</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            {data.accounts.length === 0 ? (
              <p className="text-[var(--neu-text-secondary)]">Connect SimpleFIN in Settings to see accounts.</p>
            ) : (
              data.accounts.slice(0, 6).map((acct) => (
                <div key={acct.id} className="neu-inset-sm p-4">
                  <p className="text-sm text-[var(--neu-text-secondary)] m-0">{acct.institution_name || acct.type}</p>
                  <p className="font-medium m-0 mt-1">{acct.name}</p>
                  <p className="text-xl tabular-nums mt-2 mb-0">{formatCurrency(acct.current_balance)}</p>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="neu-raised p-6">
          <h2 className="text-lg mt-0 mb-2">Top spending</h2>
          {donutData.length === 0 ? (
            <p className="text-[var(--neu-text-secondary)] text-sm">No spending data yet.</p>
          ) : (
            <>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={donutData} dataKey="value" innerRadius={45} outerRadius={70} paddingAngle={2}>
                      {donutData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-2 mt-2 p-0 list-none">
                {data.top_categories.map((c) => (
                  <li key={c.category} className="flex justify-between text-sm">
                    <span>{c.category}</span>
                    <span className="tabular-nums">{formatCurrency(c.total)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
