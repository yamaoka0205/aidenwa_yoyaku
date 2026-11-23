import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { ApplyPage } from './pages/ApplyPage'
import { LandingPage } from './pages/LandingPage'
import { LedgerPage } from './pages/LedgerPage'
import { LoginPage } from './pages/LoginPage'
import { OperatorLoginPage } from './pages/OperatorLoginPage'
import { OperatorPage } from './pages/OperatorPage'
import { SettingsPage } from './pages/SettingsPage'

function StoreProtected({ children }: { children: React.ReactNode }) {
  const { loading, session } = useAuth()
  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card">読み込み中…</div>
      </div>
    )
  }
  if (!session) return <Navigate to="/login" replace />
  if (session.role === 'operator') return <Navigate to="/operator" replace />
  return <>{children}</>
}

function Shell({ onToast }: { onToast: (message: string) => void }) {
  const { session, logout } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)

  async function onLogout() {
    setLoggingOut(true)
    try {
      await logout()
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <div className="app-shell">
      <nav className="nav" aria-label="メインメニュー">
        <div className="nav-brand">
          予約
          <br />
          台帳
        </div>
        <NavLink to="/app" end className={({ isActive }) => (isActive ? 'active' : undefined)}>
          <span className="icon" aria-hidden>
            ▣
          </span>
          予約
        </NavLink>
        <NavLink to="/app/settings" className={({ isActive }) => (isActive ? 'active' : undefined)}>
          <span className="icon" aria-hidden>
            ⚙
          </span>
          設定
        </NavLink>
        <div className="nav-footer">
          <div className="nav-user" title={session?.email}>
            {session?.displayName || 'ユーザー'}
          </div>
          <button type="button" className="nav-logout" onClick={() => void onLogout()} disabled={loggingOut}>
            {loggingOut ? '…' : 'ログアウト'}
          </button>
        </div>
      </nav>

      <main className="main">
        <Routes>
          <Route path="/app" element={<LedgerPage onToast={onToast} />} />
          <Route path="/app/settings" element={<SettingsPage onToast={onToast} />} />
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(null), 2200)
    return () => window.clearTimeout(t)
  }, [toast])

  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/apply" element={<ApplyPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/operator/login" element={<OperatorLoginPage />} />
        <Route path="/operator" element={<OperatorPage onToast={setToast} />} />
        <Route
          path="/app/*"
          element={
            <StoreProtected>
              <Shell onToast={setToast} />
            </StoreProtected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {toast ? (
        <div className="success-toast" role="status">
          <div className="success-card">
            <div className="check">✓</div>
            <h3>完了</h3>
            <p>{toast}</p>
          </div>
        </div>
      ) : null}
    </AuthProvider>
  )
}
