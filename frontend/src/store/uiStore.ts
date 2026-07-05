import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIStore {
  theme: 'light' | 'dark'
  sidebarCollapsed: boolean
  toggleTheme: () => void
  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark') => void
}

export const useUiStore = create<UIStore>()(
  persist(
    (set, get) => ({
      theme: 'light',
      sidebarCollapsed: false,

      toggleTheme: () => {
        const next = get().theme === 'light' ? 'dark' : 'light'
        set({ theme: next })
        document.documentElement.classList.toggle('dark', next === 'dark')
      },

      setTheme: (theme) => {
        set({ theme })
        document.documentElement.classList.toggle('dark', theme === 'dark')
      },

      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: 'finance-ui',
      onRehydrateStorage: () => (state) => {
        // Apply theme class on page load from persisted store
        if (state?.theme === 'dark') {
          document.documentElement.classList.add('dark')
        }
      },
    }
  )
)
