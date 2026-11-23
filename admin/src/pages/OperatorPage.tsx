import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { listApplications, reviewApplication, type ApplicationItem } from '../api'
import { useAuth } from '../auth'

export function OperatorPage({ onToast }: { onToast: (message: string) => void }) {
  const { session, loading, logout } = useAuth()
  const [items, setItems] = useState<ApplicationItem[]>([])
  const [filter, setFilter] = useState<'pending' | 'all' | 'approved' | 'rejected'>('pending')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastCreds, setLastCreds] = useState<{ email: string; password: string } | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const res = await listApplications(filter)
      setItems(res.applications)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'load_failed')
    }
  }, [filter])

  useEffect(() => {
    if (session?.role === 'operator') void refresh()
  }, [session, refresh])

  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card">読み込み中…</div>
      </div>
    )
  }
  if (!session) return <Navigate to="/operator/login" replace />
  if (session.role !== 'operator') return <Navigate to="/app" replace />

  async function onReview(id: string, decision: 'approve' | 'reject') {
    setBusyId(id)
    setError(null)
    try {
      const reason =
        decision === 'reject' ? window.prompt('却下理由（任意）') || '' : undefined
      const res = await reviewApplication({
        applicationId: id,
        decision,
        rejectReason: reason,
      })
      if (decision === 'approve' && res.temporaryPassword) {
        const email = res.application?.contactEmail || ''
        setLastCreds({ email, password: res.temporaryPassword })
        onToast('承認しました。仮パスワードを控えてください')
      } else {
        onToast(decision === 'approve' ? '承認しました' : '却下しました')
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'review_failed')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="operator-shell">
      <header className="operator-top">
        <div>
          <Link to="/" className="operator-brand">
            よやく台帳
          </Link>
          <p className="operator-sub">申し込み承認</p>
        </div>
        <div className="operator-actions">
          <span className="nav-user">{session.displayName}</span>
          <button type="button" className="btn btn-ghost" onClick={() => void logout()}>
            ログアウト
          </button>
        </div>
      </header>

      <main className="operator-main">
        <div className="filter-row">
          {(['pending', 'approved', 'rejected', 'all'] as const).map((f) => (
            <button
              key={f}
              type="button"
              className={filter === f ? 'chip active' : 'chip'}
              onClick={() => setFilter(f)}
            >
              {f === 'pending'
                ? '未処理'
                : f === 'approved'
                  ? '承認済'
                  : f === 'rejected'
                    ? '却下'
                    : 'すべて'}
            </button>
          ))}
        </div>

        {error ? <div className="alert alert-error">{error}</div> : null}

        {lastCreds ? (
          <div className="cred-banner" role="status">
            <strong>店舗ログイン情報（この画面でのみ表示）</strong>
            <p>
              メール <code>{lastCreds.email}</code>
              <br />
              仮パスワード <code>{lastCreds.password}</code>
            </p>
            <button type="button" className="btn btn-ghost" onClick={() => setLastCreds(null)}>
              閉じる
            </button>
          </div>
        ) : null}

        {items.length === 0 ? (
          <p className="empty-state">該当する申し込みはありません</p>
        ) : (
          <ul className="app-list">
            {items.map((app) => (
              <li key={app.applicationId} className="app-item">
                <div className="app-item-main">
                  <h2>{app.storeName}</h2>
                  <p>
                    {app.contactName} · {app.contactEmail}
                    {app.contactPhone ? ` · ${app.contactPhone}` : ''}
                  </p>
                  {app.note ? <p className="app-note">{app.note}</p> : null}
                  <p className="app-meta">
                    {app.status} · {app.createdAt}
                    {app.tenantId ? ` · ${app.tenantId}` : ''}
                  </p>
                </div>
                {app.status === 'pending' ? (
                  <div className="app-item-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busyId === app.applicationId}
                      onClick={() => void onReview(app.applicationId, 'approve')}
                    >
                      承認
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={busyId === app.applicationId}
                      onClick={() => void onReview(app.applicationId, 'reject')}
                    >
                      却下
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
