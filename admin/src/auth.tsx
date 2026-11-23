import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import {
  authMe,
  login as apiLogin,
  logout as apiLogout,
  setStoredToken,
  getStoredToken,
  type AuthSession,
} from './api'

type AuthState = {
  loading: boolean
  session: AuthSession | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState<AuthSession | null>(null)

  useEffect(() => {
    const token = getStoredToken()
    if (!token) {
      setLoading(false)
      return
    }
    authMe()
      .then((me) => setSession(me))
      .catch(() => {
        setStoredToken(null)
        setSession(null)
      })
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const res = await apiLogin(email, password)
    setStoredToken(res.accessToken)
    setSession({
      status: 'ok',
      userId: res.userId,
      tenantId: res.tenantId,
      displayName: res.displayName,
      email: res.email,
      role: res.role,
      storeName: res.storeName,
    })
  }

  async function logout() {
    try {
      await apiLogout()
    } catch {
      // clear local anyway
    }
    setStoredToken(null)
    setSession(null)
  }

  return (
    <AuthContext.Provider value={{ loading, session, login, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
