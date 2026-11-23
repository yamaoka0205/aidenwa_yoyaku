import type { ListReservationsResponse, Store, StoreFaq, StoreHours } from './types'
import { PRODUCTION_API_BASE } from './deployConfig'

const TOKEN_KEY = 'bookingapp.accessToken'

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export type AuthSession = {
  status: string
  userId: string
  tenantId: string
  displayName: string
  email: string
  role: string
  storeName?: string
  accessToken?: string
}

function baseUrl(): string {
  if (import.meta.env.DEV) return '/api'
  const fromEnv = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '')
  if (fromEnv) return fromEnv
  return PRODUCTION_API_BASE
}

async function post<T>(
  path: string,
  body: Record<string, unknown> = {},
  opts?: { auth?: boolean },
): Promise<T> {
  const headers: Record<string, string> = { 'content-type': 'application/json' }
  if (opts?.auth !== false) {
    const token = getStoredToken()
    if (token) headers.authorization = `Bearer ${token}`
  }
  const res = await fetch(`${baseUrl()}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  const data = (await res.json()) as T & { status?: string; reason?: string }
  if (!res.ok) {
    const reason = data?.reason || data?.status || res.statusText
    throw new Error(String(reason))
  }
  return data
}

export function login(email: string, password: string) {
  return post<AuthSession & { accessToken: string; storeName?: string }>(
    '/auth/login',
    { email, password },
    { auth: false },
  )
}

export function logout() {
  return post<{ status: string }>('/auth/logout', {})
}

export function authMe() {
  return post<AuthSession>('/auth/me', {})
}

export function listReservations(date: string) {
  return post<ListReservationsResponse>('/reservations/list', { date })
}

export function getStore() {
  return post<Store>('/store/get', {})
}

export function updateStore(input: {
  name?: string
  standardDurationMin?: number
  hours?: StoreHours[]
  faqs?: StoreFaq[]
}) {
  return post<Store>('/store/update', { ...input })
}

export function checkAvailability(input: {
  date: string
  startTime: string
  partySize: number
}) {
  return post<{
    status: string
    endTime?: string
    tableId?: string
    reason?: string
    standardDurationMin?: number
  }>('/availability/check', {
    date: input.date,
    startTime: input.startTime,
    partySize: input.partySize,
  })
}

export function confirmReservation(input: {
  date: string
  startTime: string
  partySize: number
  customerName: string
  customerPhone?: string
}) {
  return post<{
    status: string
    reservationId?: string
    endTime?: string
    tableId?: string
    reason?: string
  }>('/reservations/confirm', {
    date: input.date,
    startTime: input.startTime,
    partySize: input.partySize,
    customerName: input.customerName,
    customerPhone: input.customerPhone || undefined,
    source: 'manual',
  })
}

export type ApplicationItem = {
  applicationId: string
  status: string
  storeName: string
  contactName: string
  contactEmail: string
  contactPhone?: string
  note?: string
  createdAt?: string
  reviewedAt?: string
  tenantId?: string
  rejectReason?: string
}

export function createApplication(input: {
  storeName: string
  contactName: string
  contactEmail: string
  contactPhone?: string
  note?: string
}) {
  return post<{ status: string; applicationId: string; message?: string }>(
    '/applications/create',
    { ...input },
    { auth: false },
  )
}

export function listApplications(status: string = 'pending') {
  return post<{ status: string; count: number; applications: ApplicationItem[] }>(
    '/applications/list',
    { status },
  )
}

export function reviewApplication(input: {
  applicationId: string
  decision: 'approve' | 'reject'
  rejectReason?: string
}) {
  return post<{
    status: string
    application?: ApplicationItem
    tenantId?: string
    temporaryPassword?: string
    userId?: string
  }>('/applications/review', { ...input })
}
