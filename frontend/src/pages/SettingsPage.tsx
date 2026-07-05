import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { settingsApi, simplefinApi } from '@/lib/hooks'
import { useUiStore } from '@/store/uiStore'

export default function SettingsPage() {
  const qc = useQueryClient()
  const { theme, setTheme } = useUiStore()
  const [setupToken, setSetupToken] = useState('')
  const [transferWindow, setTransferWindow] = useState<number | null>(null)

  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: settingsApi.get })
  const { data: simplefinStatus } = useQuery({ queryKey: ['simplefin-status'], queryFn: simplefinApi.status })

  const saveSettings = useMutation({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      toast.success('Settings saved')
    },
  })

  const syncNow = useMutation({
    mutationFn: simplefinApi.sync,
    onSuccess: (res) => {
      qc.invalidateQueries()
      toast.success(`Sync complete${res.new_transactions != null ? ` (+${res.new_transactions} new)` : ''}`)
    },
    onError: () => toast.error('Sync failed'),
  })

  const setupSimplefin = useMutation({
    mutationFn: () => simplefinApi.setup(),
    onSuccess: () => {
      qc.invalidateQueries()
      toast.success('SimpleFIN connected — initial sync started')
    },
    onError: () => toast.error('Setup failed — token may already be claimed'),
  })

  const reconnect = useMutation({
    mutationFn: () => settingsApi.reconnect(setupToken || undefined),
    onSuccess: () => {
      qc.invalidateQueries()
      toast.success('Reconnected and synced')
    },
    onError: () => toast.error('Reconnect failed'),
  })

  const currentWindow = transferWindow ?? settings?.transfer_window_days ?? 2

  return (
    <div className="space-y-6 max-w-3xl">
      <header>
        <h1 className="text-3xl m-0">Settings</h1>
        <p className="text-[var(--neu-text-secondary)] mt-1">SimpleFIN, categorization, and appearance</p>
      </header>

      <section className="neu-raised p-6 space-y-4">
        <h2 className="text-lg m-0">SimpleFIN connection</h2>
        <div className="neu-inset-sm p-4 text-sm text-[var(--neu-text-secondary)] space-y-2">
          <p className="m-0">
            SimpleFIN Bridge only returns <strong>90 days of transactions per API call</strong>.
            Initial sync walks backward in chunks; ongoing syncs pull recent changes only.
            History beyond what BofA exposes (~90 days right now) won&apos;t appear.
          </p>
          <p className="m-0">
            If the app shows connected below, you&apos;re done — no need to copy anything to <code className="text-xs">.env</code>.
          </p>
        </div>
        <p className="text-sm text-[var(--neu-text-secondary)] m-0">
          Status: {simplefinStatus?.connected ? simplefinStatus.status : 'Not connected'}
          {simplefinStatus?.last_sync_at && ` · Last sync ${new Date(simplefinStatus.last_sync_at).toLocaleString()}`}
        </p>

        {!simplefinStatus?.connected && (
          <button type="button" className="neu-btn neu-btn-accent px-4 py-2" onClick={() => setupSimplefin.mutate()}>
            Connect using env token
          </button>
        )}

        <div className="flex flex-wrap gap-3">
          <button type="button" className="neu-btn px-4 py-2" onClick={() => syncNow.mutate()} disabled={!simplefinStatus?.connected}>
            Sync now
          </button>
        </div>

        <div className="space-y-2 pt-2">
          <label className="text-sm block">New setup token (one-time claim)</label>
          <input
            className="neu-input w-full px-3 py-2 text-sm"
            placeholder="Paste new SIMPLEFIN_TOKEN to rotate"
            value={setupToken}
            onChange={(e) => setSetupToken(e.target.value)}
          />
          <button type="button" className="neu-btn px-4 py-2 text-sm" onClick={() => reconnect.mutate()}>
            Re-claim & sync
          </button>
        </div>
      </section>

      <section className="neu-raised p-6 space-y-4">
        <h2 className="text-lg m-0">Transfer detection</h2>
        <p className="text-sm text-[var(--neu-text-secondary)] m-0">
          Match opposite-sign transactions across accounts within this many days.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            className="neu-input w-32 px-3 py-2"
            type="number"
            min={0}
            max={14}
            value={currentWindow}
            onChange={(e) => setTransferWindow(Number(e.target.value))}
          />
          <button
            type="button"
            className="neu-btn px-4 py-2"
            onClick={() => saveSettings.mutate({ transfer_window_days: currentWindow })}
          >
            Save
          </button>
        </div>
      </section>

      <section className="neu-raised p-6 space-y-4">
        <h2 className="text-lg m-0">Appearance</h2>
        <div className="neu-segment">
          <button type="button" className={`neu-segment-item ${theme === 'light' ? 'active' : ''}`} onClick={() => setTheme('light')}>
            Light
          </button>
          <button type="button" className={`neu-segment-item ${theme === 'dark' ? 'active' : ''}`} onClick={() => setTheme('dark')}>
            Dark
          </button>
        </div>
      </section>
    </div>
  )
}
