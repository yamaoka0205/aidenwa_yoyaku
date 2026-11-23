import { useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

export function LoginPage() {
  const { session, loading, login } = useAuth()
  const [email, setEmail] = useState('demo@sakura.local')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && session?.role === 'operator') return <Navigate to="/operator" replace />
  if (!loading && session) return <Navigate to="/app" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email.trim(), password)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'login_failed'
      setError(
        msg === 'invalid_credentials'
          ? 'メールまたはパスワードが違います'
          : msg === 'no_membership'
            ? 'このアカウントに店舗が割り当てられていません'
            : 'ログインできませんでした。もう一度お試しください',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <p className="login-eyebrow">店舗向け予約台帳</p>
        <h1>ログイン</h1>
        <p className="login-lead">店の予約と設定を見るには、ログインしてください。</p>

        {error ? <div className="alert alert-error">{error}</div> : null}

        <div className="field">
          <label htmlFor="email">メールアドレス</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">パスワード</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting || loading}>
          {submitting ? '確認中…' : 'ログイン'}
        </button>

        <details className="demo-hint">
          <summary>デモ用アカウント（Cognito）</summary>
          <p>
            メール <code>demo@sakura.local</code>
            <br />
            パスワード <code>Demo-pass-2026!</code>
          </p>
        </details>

        <p className="login-links">
          <Link to="/apply">店舗を申し込む</Link>
          {' · '}
          <Link to="/">紹介ページ</Link>
        </p>
      </form>
    </div>
  )
}
