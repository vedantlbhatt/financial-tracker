import { useQuery } from '@tanstack/react-query'
import { accountsApi } from '@/lib/hooks'
import { formatCurrency } from '@/lib/format'

export default function AccountsPage() {
  const { data: accounts, isLoading } = useQuery({ queryKey: ['accounts'], queryFn: accountsApi.list })

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl m-0">Accounts</h1>
        <p className="text-[var(--neu-text-secondary)] mt-1">
          Linked via SimpleFIN Bridge — add institutions at simplefin.org
        </p>
      </header>

      {isLoading ? (
        <div className="neu-raised p-8">Loading accounts...</div>
      ) : !accounts?.length ? (
        <div className="neu-raised p-8">
          <p className="m-0">No accounts synced yet.</p>
          <p className="text-sm text-[var(--neu-text-secondary)] mt-2">
            Connect SimpleFIN in Settings and run a sync to pull your Bank of America accounts.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {accounts.map((acct) => (
            <div key={acct.id} className="neu-raised p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm text-[var(--neu-text-secondary)] m-0">{acct.institution_name || 'Bank'}</p>
                  <h2 className="text-lg m-0 mt-1">{acct.name}</h2>
                  <p className="text-xs text-[var(--neu-text-secondary)] mt-1 capitalize">
                    {acct.subtype || acct.type}
                  </p>
                </div>
                <span
                  className="neu-badge text-xs"
                  style={{
                    color: acct.connection_status === 'needs_attention' ? 'var(--neu-warning)' : 'var(--neu-positive)',
                  }}
                >
                  {acct.connection_status}
                </span>
              </div>

              <p className="text-3xl tabular-nums mt-6 mb-2">{formatCurrency(acct.current_balance)}</p>
              {acct.available_balance != null && (
                <p className="text-sm text-[var(--neu-text-secondary)] m-0">
                  Available: {formatCurrency(acct.available_balance)}
                </p>
              )}

              {acct.sync_errors && acct.sync_errors.length > 0 && (
                <div className="neu-inset-sm p-3 mt-4 text-sm text-[var(--neu-warning)]">
                  Needs re-link on SimpleFIN Bridge
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
