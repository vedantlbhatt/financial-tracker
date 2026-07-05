import api from './api'
import type {
  Account,
  AppSettings,
  CashFlowResponse,
  CategorySummary,
  OverviewData,
  PaginatedTransactions,
  SimplefinStatus,
} from './types'

export const overviewApi = {
  get: async () => {
    const { data } = await api.get<OverviewData>('/overview')
    return data
  },
}

export const accountsApi = {
  list: async () => {
    const { data } = await api.get<Account[]>('/accounts')
    return data
  },
}

export const transactionsApi = {
  list: async (params: Record<string, string | number | boolean | undefined>) => {
    const { data } = await api.get<PaginatedTransactions>('/transactions', { params })
    return data
  },
  updateCategory: async (transactionId: string, category: string, remember = true) => {
    await api.put(`/transactions/${transactionId}/category`, { category, remember_merchant: remember })
  },
  updateTransfer: async (transactionId: string, isTransfer: boolean) => {
    await api.put(`/transactions/${transactionId}/transfer`, { is_transfer: isTransfer })
  },
}

export const cashFlowApi = {
  get: async (params: Record<string, string | undefined>) => {
    const { data } = await api.get<CashFlowResponse>('/cash-flow', { params })
    return data
  },
}

export const categoriesApi = {
  breakdown: async (params?: Record<string, string>) => {
    const { data } = await api.get<{ categories: CategorySummary[]; period_total_outflow: number }>(
      '/categories/breakdown',
      { params },
    )
    return data
  },
  merchants: async (params?: Record<string, string | number>) => {
    const { data } = await api.get<Array<{ merchant: string; total: number; count: number }>>(
      '/categories/merchants',
      { params },
    )
    return data
  },
  trends: async (months = 6) => {
    const { data } = await api.get<Array<{ category: string; points: Array<{ month: string; total: number }> }>>(
      '/categories/trends',
      { params: { months } },
    )
    return data
  },
  available: async () => {
    const { data } = await api.get<string[]>('/categories/available')
    return data
  },
}

export const simplefinApi = {
  status: async () => {
    const { data } = await api.get<SimplefinStatus>('/simplefin/status')
    return data
  },
  setup: async () => {
    const { data } = await api.post<SimplefinStatus>('/simplefin/setup', {})
    return data
  },
  sync: async () => {
    const { data } = await api.post<{
      message: string
      new_transactions?: number
      api_calls?: number
      quota?: { requests_used_today: number; requests_remaining_today: number; daily_request_limit: number }
    }>('/simplefin/sync')
    return data
  },
}

export const settingsApi = {
  get: async () => {
    const { data } = await api.get<AppSettings>('/settings')
    return data
  },
  update: async (payload: Partial<AppSettings>) => {
    const { data } = await api.patch<AppSettings>('/settings', payload)
    return data
  },
  reconnect: async (setupToken?: string) => {
    const { data } = await api.post('/settings/simplefin/reconnect', { setup_token: setupToken })
    return data
  },
}
