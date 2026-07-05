import { NavLink } from 'react-router-dom'
import { useUiStore } from '@/store/uiStore'
import { cn } from '@/lib/format'

const links = [
  { to: '/', label: 'Overview', icon: '◉' },
  { to: '/cash-flow', label: 'Cash Flow', icon: '↕' },
  { to: '/transactions', label: 'Transactions', icon: '☰' },
  { to: '/categories', label: 'Categories', icon: '◎' },
  { to: '/accounts', label: 'Accounts', icon: '▣' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, theme, toggleTheme } = useUiStore()

  return (
    <aside
      className={cn(
        'h-screen sticky top-0 flex flex-col p-4 transition-all duration-300',
        sidebarCollapsed ? 'w-20' : 'w-64',
      )}
    >
      <div className="neu-raised p-4 mb-4 flex items-center justify-between gap-2">
        {!sidebarCollapsed && (
          <div>
            <p className="text-xs uppercase tracking-widest text-[var(--neu-text-secondary)]">Finance</p>
            <h1 className="text-lg font-semibold m-0">Tracker</h1>
          </div>
        )}
        <button type="button" className="neu-btn px-3 py-2 text-sm" onClick={toggleSidebar}>
          {sidebarCollapsed ? '»' : '«'}
        </button>
      </div>

      <nav className="neu-raised flex-1 p-3 flex flex-col gap-2">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) =>
              cn(
                'neu-btn flex items-center gap-3 px-3 py-3 text-sm no-underline',
                isActive && 'pressed text-[var(--neu-accent)]',
              )
            }
          >
            <span className="text-base">{link.icon}</span>
            {!sidebarCollapsed && <span>{link.label}</span>}
          </NavLink>
        ))}
      </nav>

      <button type="button" className="neu-btn mt-4 px-4 py-3 text-sm" onClick={toggleTheme}>
        {theme === 'dark' ? '☀ Light' : '☾ Dark'}
      </button>
    </aside>
  )
}
