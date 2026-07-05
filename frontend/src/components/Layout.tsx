import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="min-h-screen flex">
      <Sidebar />
      <main className="flex-1 p-6 lg:p-8 overflow-auto page-enter">
        <Outlet />
      </main>
    </div>
  )
}
