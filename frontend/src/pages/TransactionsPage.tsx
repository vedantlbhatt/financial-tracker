import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { accountsApi, categoriesApi, transactionsApi } from '@/lib/hooks'
import { formatCurrency, cn } from '@/lib/format'

export default function TransactionsPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [accountId, setAccountId] = useState('')
  const [category, setCategory] = useState('')
  const [uncategorizedOnly, setUncategorizedOnly] = useState(false)
  const [includeTransfers, setIncludeTransfers] = useState(true)

  const { data: accounts } = useQuery({ queryKey: ['accounts'], queryFn: accountsApi.list })
  const { data: categories } = useQuery({ queryKey: ['categories'], queryFn: categoriesApi.available })

  const { data, isLoading } = useQuery({
    queryKey: ['transactions', page, search, accountId, category, uncategorizedOnly, includeTransfers],
    queryFn: () =>
      transactionsApi.list({
        page,
        page_size: 30,
        search: search || undefined,
        account_id: accountId || undefined,
        category: category || undefined,
        uncategorized_only: uncategorizedOnly,
        include_transfers: includeTransfers,
      }),
  })

  const categoryMutation = useMutation({
    mutationFn: ({ txId, cat }: { txId: string; cat: string }) => transactionsApi.updateCategory(txId, cat),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['overview'] })
      qc.invalidateQueries({ queryKey: ['categories'] })
      toast.success('Category updated')
    },
  })

  const transferMutation = useMutation({
    mutationFn: ({ txId, isTransfer }: { txId: string; isTransfer: boolean }) =>
      transactionsApi.updateTransfer(txId, isTransfer),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['cash-flow'] })
      qc.invalidateQueries({ queryKey: ['overview'] })
      toast.success('Transfer flag updated')
    },
  })

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl m-0">Transactions</h1>
        <p className="text-[var(--neu-text-secondary)] mt-1">Search, filter, and categorize</p>
      </header>

      <div className="neu-raised p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <input
          className="neu-input px-3 py-2"
          placeholder="Search description or payee"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
        />
        <select className="neu-input px-3 py-2" value={accountId} onChange={(e) => { setAccountId(e.target.value); setPage(1) }}>
          <option value="">All accounts</option>
          {(accounts || []).map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        <select className="neu-input px-3 py-2" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1) }}>
          <option value="">All categories</option>
          {(categories || []).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <div className="flex flex-wrap gap-3 items-center">
          <label className="text-sm flex items-center gap-2">
            <input type="checkbox" checked={uncategorizedOnly} onChange={(e) => setUncategorizedOnly(e.target.checked)} />
            Uncategorized
          </label>
          <label className="text-sm flex items-center gap-2">
            <input type="checkbox" checked={includeTransfers} onChange={(e) => setIncludeTransfers(e.target.checked)} />
            Show transfers
          </label>
        </div>
      </div>

      <div className="neu-raised overflow-hidden">
        {isLoading ? (
          <p className="p-6">Loading...</p>
        ) : !data?.items.length ? (
          <p className="p-6 text-[var(--neu-text-secondary)]">No transactions found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--neu-text-secondary)]">
                  <th className="p-4 font-medium">Date</th>
                  <th className="p-4 font-medium">Payee</th>
                  <th className="p-4 font-medium">Account</th>
                  <th className="p-4 font-medium">Category</th>
                  <th className="p-4 font-medium text-right">Amount</th>
                  <th className="p-4 font-medium">Flags</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((tx) => (
                  <tr
                    key={tx.id}
                    className={cn(
                      'border-t border-[var(--neu-border)]',
                      tx.is_transfer && 'opacity-60',
                    )}
                  >
                    <td className="p-4 whitespace-nowrap">{tx.date}</td>
                    <td className="p-4">
                      <div className="font-medium">{tx.payee || tx.description}</div>
                      {tx.memo && <div className="text-xs text-[var(--neu-text-secondary)]">{tx.memo}</div>}
                    </td>
                    <td className="p-4">{tx.account_name}</td>
                    <td className="p-4">
                      <select
                        className="neu-input px-2 py-1 text-xs"
                        value={tx.category}
                        onChange={(e) => categoryMutation.mutate({ txId: tx.transaction_id, cat: e.target.value })}
                      >
                        {(categories || [tx.category]).map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </td>
                    <td
                      className="p-4 text-right tabular-nums font-medium"
                      style={{ color: tx.amount >= 0 ? 'var(--neu-positive)' : 'var(--neu-negative)' }}
                    >
                      {formatCurrency(tx.amount)}
                    </td>
                    <td className="p-4">
                      <button
                        type="button"
                        className={cn('neu-badge text-xs', tx.is_transfer && 'text-[var(--neu-warning)]')}
                        onClick={() => transferMutation.mutate({ txId: tx.transaction_id, isTransfer: !tx.is_transfer })}
                      >
                        {tx.is_transfer ? 'Transfer ✓' : 'Mark transfer'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {data && data.total > data.page_size && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-[var(--neu-text-secondary)]">{data.total} transactions</p>
          <div className="flex flex-wrap gap-3">
            <button type="button" className="neu-btn px-4 py-2 text-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="neu-inset-sm px-4 py-2 text-sm">{page} / {totalPages}</span>
            <button type="button" className="neu-btn px-4 py-2 text-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
