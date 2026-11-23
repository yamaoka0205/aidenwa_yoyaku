import { useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

export function OperatorLoginPage() {
  const { session, loading, login } = useAuth()
  const [email, setEmail] = useState('operator@sakura.local')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && session?.role === 'operator') {
    return <Navigate to="/operator" replace />
  }
  if (!loading && session && session.role !== 'operator') {
    return <Navigate to="/app" replace />
  }

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
            ? '運営者アカウントではありません'
            : 'ログインできませんでした',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <p className="login-eyebrow">運営者 · よやく台帳</p>
        <h1>運営ログイン</h1>
        <p className="login-lead">店舗申し込みの承認・却下を行います。</p>

        {error ? <div className="alert alert-error">{error}</div> : null}

        <div className="field">
          <label htmlFor="op-email">メールアドレス</label>
          <input
            id="op-email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="op-password">パスワード</label>
          <input
            id="op-password"
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
          <summary>デモ用運営アカウント</summary>
          <p>
            メール <code>operator@sakura.local</code>
            <br />
            パスワード <code>Demo-pass-2026!</code>
          </p>
        </details>

        <p className="login-links">
          <Link to="/">紹介ページ</Link>
        </p>
      </form>
    </div>
  )
}
