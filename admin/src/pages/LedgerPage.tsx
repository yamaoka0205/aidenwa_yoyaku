import { useCallback, useEffect, useState } from 'react'
import { getStore, listReservations } from '../api'
import { formatDateLabel, shiftDate, todayInTokyo } from '../dates'
import { ReservationSheet } from '../components/ReservationSheet'
import type { Reservation, Store } from '../types'

type Props = {
  onToast: (message: string) => void
}

export function LedgerPage({ onToast }: Props) {
  const [date, setDate] = useState(todayInTokyo())
  const [rows, setRows] = useState<Reservation[]>([])
  const [count, setCount] = useState(0)
  const [partyTotal, setPartyTotal] = useState(0)
  const [store, setStore] = useState<Store | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [list, storeRes] = await Promise.all([listReservations(date), getStore()])
      setRows(list.reservations || [])
      setCount(list.count || 0)
      setPartyTotal(list.partyTotal || 0)
      setStore(storeRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : '読み込みに失敗しました')
    } finally {
      setLoading(false)
    }
  }, [date])

  useEffect(() => {
    void reload()
  }, [reload])

  return (
    <>
      <header className="topbar">
        <div>
          <h1>今日の予約</h1>
          <div className="store-chip" style={{ marginTop: 8 }}>
            {store?.name || '店舗を読み込み中…'}
          </div>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setSheetOpen(true)}>
          ＋ 予約を入れる
        </button>
      </header>

      <div className="content">
        {error ? <div className="status-banner">読み込みエラー: {error}</div> : null}

        <div className="toolbar">
          <div className="date-nav">
            <button type="button" aria-label="前日" onClick={() => setDate((d) => shiftDate(d, -1))}>
              ‹
            </button>
            <div className="date-label">{formatDateLabel(date)}</div>
            <button type="button" aria-label="翌日" onClick={() => setDate((d) => shiftDate(d, 1))}>
              ›
            </button>
          </div>
          <button type="button" className="btn btn-ghost" onClick={() => setDate(todayInTokyo())}>
            今日
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => void reload()} disabled={loading}>
            更新
          </button>
        </div>

        <div className="summary">
          <div className="summary-card">
            <div className="label">予約</div>
            <div className="value">
              {count}
              <span className="unit">組</span>
            </div>
          </div>
          <div className="summary-card">
            <div className="label">人数合計</div>
            <div className="value">
              {partyTotal}
              <span className="unit">名</span>
            </div>
          </div>
          <div className="summary-card">
            <div className="label">利用時間</div>
            <div className="value" style={{ fontSize: 22 }}>
              {store ? `${store.standardDurationMin}分` : '—'}
            </div>
          </div>
        </div>

        <div className="ledger">
          {loading ? (
            <div className="ledger-empty">読み込み中…</div>
          ) : rows.length === 0 ? (
            <div className="ledger-empty">
              <strong>この日の予約はまだありません</strong>
              右上の「予約を入れる」か、電話AIからの予約がここに並びます。
            </div>
          ) : (
            rows.map((r) => (
              <div className="res-row" key={r.reservationId}>
                <div className="res-time">{r.startTime}</div>
                <div className="res-party">{r.partySize}</div>
                <div>
                  <div className="res-name">{r.customerName} 様</div>
                  <div className="res-meta">
                    <span>
                      {r.startTime}〜{r.endTime}
                    </span>
                    <span>{r.tableId || '卓未定'}</span>
                    {r.customerPhone ? <span>{r.customerPhone}</span> : null}
                    <span className={`badge ${r.source === 'ai_phone' ? 'badge-phone' : 'badge-manual'}`}>
                      {r.source === 'ai_phone' ? '電話AI' : '手入力'}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <ReservationSheet
        open={sheetOpen}
        date={date}
        store={store}
        onClose={() => setSheetOpen(false)}
        onCreated={(summary) => {
          onToast(summary)
          void reload()
        }}
      />
    </>
  )
}
