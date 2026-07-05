export interface User {
  id: string
  email: string
}

export interface Account {
  id: string
  account_id: string
  name: string
  institution_name: string | null
  type: string
  subtype: string | null
  current_balance: number | null
  available_balance: number | null
  iso_currency_code: string
  connection_status: string
  sync_errors: unknown[] | null
}

export interface Transaction {
  id: string
  transaction_id: string
  account_id: string
  account_name: string
  amount: number
  date: string
  description: string
  payee: string | null
  memo: string | null
  category: string
  auto_category: string | null
  is_transfer: boolean
  user_category: string | null
}

export interface PaginatedTransactions {
  items: Transaction[]
  total: number
  page: number
  page_size: number
}

export interface CashFlowBucket {
  date: string
  inflow: number
  outflow: number
  net: number
  cumulative_net: number
}

export interface CashFlowResponse {
  buckets: CashFlowBucket[]
  summary: { total_inflow: number; total_outflow: number; net: number }
  granularity: string
}

export interface CategorySummary {
  category: string
  total: number
  count: number
  percentage: number
}

export interface IncomeDeposit {
  date: string
  amount: number
  payee: string
  category: string
}

export interface OverviewData {
  net_worth: number
  month_inflow: number
  month_outflow: number
  month_net: number
  month_sparkline: number[]
  ytd_inflow: number
  ytd_outflow: number
  ytd_net: number
  recent_income: IncomeDeposit[]
  accounts: Array<{
    id: string
    name: string
    type: string
    subtype: string | null
    current_balance: number | null
    institution_name: string | null
  }>
  top_categories: Array<{ category: string; total: number; percentage: number }>
  simplefin_status: string | null
  account_errors: unknown[] | null
  last_sync_at: string | null
}

export interface SimplefinStatus {
  connected: boolean
  status: string | null
  last_sync_at: string | null
  account_errors: unknown[] | null
}

export interface AppSettings {
  transfer_window_days: number
  simplefin_connected: boolean
  simplefin_status: string | null
  last_sync_at: string | null
}
