import { Outlet } from 'react-router-dom'
import Header from './Header'

export default function Layout() {
  return (
    <div className="app-shell">
      <Header />
      <main className="page-wrap">
        <Outlet />
      </main>
      <footer className="footer">
        <span>KAYKAYNMYDU</span>
      </footer>
    </div>
  )
}
