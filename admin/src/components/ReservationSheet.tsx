import { useEffect, useMemo, useState } from 'react'
import { checkAvailability, confirmReservation } from '../api'
import { buildTimeChips } from '../dates'
import type { Store } from '../types'

type Props = {
  open: boolean
  date: string
  store: Store | null
  onClose: () => void
  onCreated: (summary: string) => void
}

export function ReservationSheet({ open, date, store, onClose, onCreated }: Props) {
  const [partySize, setPartySize] = useState(2)
  const [startTime, setStartTime] = useState('19:00')
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [checking, setChecking] = useState(false)
  const [saving, setSaving] = useState(false)
  const [avail, setAvail] = useState<{ status: string; endTime?: string; tableId?: string; reason?: string } | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  const hours = useMemo(() => {
    if (!store) return null
    const dow = new Date(`${date}T12:00:00`).getDay()
    const keys = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
    return store.hours.find((h) => h.dow === keys[dow]) || null
  }, [store, date])

  const timeChips = useMemo(() => {
    if (!hours || hours.isClosed) return []
    return buildTimeChips(
      hours.openTime || '11:00',
      hours.closeTime || '22:00',
      hours.lastStartTime || '20:00',
      30,
    )
  }, [hours])

  useEffect(() => {
    if (!open) return
    setPartySize(2)
    setCustomerName('')
    setCustomerPhone('')
    setError(null)
    setAvail(null)
    setStartTime(timeChips.includes('19:00') ? '19:00' : timeChips[0] || '19:00')
  }, [open, date, timeChips])

  useEffect(() => {
    if (!open || !startTime || !partySize) return
    let cancelled = false
    setChecking(true)
    setError(null)
    const t = window.setTimeout(() => {
      checkAvailability({ date, startTime, partySize })
        .then((res) => {
          if (!cancelled) setAvail(res)
        })
        .catch((err: Error) => {
          if (!cancelled) {
            setAvail(null)
            setError(err.message || '空席確認に失敗しました')
          }
        })
        .finally(() => {
          if (!cancelled) setChecking(false)
        })
    }, 200)
    return () => {
      cancelled = true
      window.clearTimeout(t)
    }
  }, [open, date, startTime, partySize])

  if (!open) return null

  const canSave =
    customerName.trim().length > 0 &&
    !!startTime &&
    partySize >= 1 &&
    partySize <= 6 &&
    avail?.status === 'available' &&
    !saving

  async function onSubmit() {
    if (!canSave) return
    setSaving(true)
    setError(null)
    try {
      const res = await confirmReservation({
        date,
        startTime,
        partySize,
        customerName: customerName.trim(),
        customerPhone: customerPhone.trim() || undefined,
      })
      if (res.status !== 'confirmed') {
        setError(statusMessage(res.status, res.reason))
        setAvail(res)
        return
      }
      onCreated(
        `${date} ${startTime}〜${res.endTime || ''}  ${partySize}名  ${customerName.trim()}様  ${res.tableId || ''}`.trim(),
      )
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '登録に失敗しました')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <aside className="sheet" role="dialog" aria-label="新規予約">
        <div className="sheet-head">
          <h2>新規予約</h2>
          <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="閉じる">
            ×
          </button>
        </div>
        <div className="sheet-body">
          {hours?.isClosed ? <div className="alert alert-warn">この日は定休日です</div> : null}
          {error ? <div className="alert alert-error">{error}</div> : null}

          <div className="field">
            <label>
              人数 <span className="hint">必須</span>
            </label>
            <div className="chips">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`chip ${partySize === n ? 'selected' : ''}`}
                  onClick={() => setPartySize(n)}
                >
                  {n}
                </button>
              ))}
            </div>
            <p className="hint" style={{ marginTop: 8 }}>
              7名以上は電話でスタッフ対応（AI予約対象外）
            </p>
          </div>

          <div className="field">
            <label>
              時刻 <span className="hint">必須・空きのある候補</span>
            </label>
            <div className="chips">
              {timeChips.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`chip ${startTime === t ? 'selected' : ''}`}
                  onClick={() => setStartTime(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label>
              お名前 <span className="hint">必須・名字だけでも可</span>
            </label>
            <input
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="ヤマダ"
              autoComplete="name"
            />
          </div>

          <div className="field">
            <label>
              電話番号 <span className="hint">任意</span>
            </label>
            <input
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              placeholder="09012345678"
              inputMode="tel"
            />
          </div>

          <div className="alert alert-warn" style={{ background: '#f0fdfa', borderColor: '#99f6e4', color: '#115e59' }}>
            {checking
              ? '空席を確認しています…'
              : avail?.status === 'available'
                ? `空いています（${avail.endTime || ''}まで・卓 ${avail.tableId || '自動'}）`
                : statusMessage(avail?.status, avail?.reason)}
          </div>
        </div>
        <div className="sheet-foot">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            やめる
          </button>
          <button type="button" className="btn btn-primary" style={{ flex: 1 }} disabled={!canSave} onClick={onSubmit}>
            {saving ? '登録中…' : '予約を確定する'}
          </button>
        </div>
      </aside>
    </>
  )
}

function statusMessage(status?: string, reason?: string): string {
  switch (status) {
    case 'available':
      return '空いています'
    case 'full':
      return 'この時間は満席です。別の時刻を選んでください'
    case 'closed':
      return '定休日です'
    case 'outside_hours':
      return '営業時間外です'
    case 'invalid_slot':
      return 'この時刻は予約できません'
    case 'human_handoff':
      return '7名以上はスタッフ対応が必要です'
    case 'not_found':
      return '店舗が見つかりません'
    default:
      return reason || '空席を確認できませんでした'
  }
}
