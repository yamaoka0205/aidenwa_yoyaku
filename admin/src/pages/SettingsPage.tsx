import { useEffect, useState } from 'react'
import { getStore, updateStore } from '../api'
import type { Store, StoreFaq, StoreHours } from '../types'

type Props = {
  onToast: (message: string) => void
}

const DURATION_OPTIONS = [60, 90, 120, 150, 180]

export function SettingsPage({ onToast }: Props) {
  const [store, setStore] = useState<Store | null>(null)
  const [name, setName] = useState('')
  const [duration, setDuration] = useState(120)
  const [hours, setHours] = useState<StoreHours[]>([])
  const [faqs, setFaqs] = useState<StoreFaq[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    getStore()
      .then((res) => {
        setStore(res)
        setName(res.name)
        setDuration(res.standardDurationMin)
        setHours(res.hours)
        setFaqs(res.faqs.length ? res.faqs : [emptyFaq(1)])
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const res = await updateStore({
        name,
        standardDurationMin: duration,
        hours,
        faqs: faqs.filter((f) => f.question.trim() || f.answer.trim()),
      })
      setStore(res)
      setHours(res.hours)
      setFaqs(res.faqs.length ? res.faqs : [emptyFaq(1)])
      onToast('設定を保存しました')
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存に失敗しました')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <>
        <header className="topbar">
          <h1>お店の設定</h1>
        </header>
        <div className="content">読み込み中…</div>
      </>
    )
  }

  return (
    <>
      <header className="topbar">
        <div>
          <h1>お店の設定</h1>
          <p style={{ margin: '6px 0 0', color: 'var(--text-muted)', fontSize: 14 }}>
            初めて使う方向けに、必要な項目だけに絞っています
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving}>
          {saving ? '保存中…' : '保存する'}
        </button>
      </header>

      <div className="content">
        {error ? <div className="status-banner">{error}</div> : null}

        <div className="settings-stack">
          <section className="settings-card">
            <h2>1. 基本</h2>
            <p className="lead">店名と、1組あたりの利用時間だけ決めます。</p>
            <div className="field">
              <label>店名</label>
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field">
              <label>標準利用時間</label>
              <div className="chips">
                {DURATION_OPTIONS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    className={`chip ${duration === m ? 'selected' : ''}`}
                    onClick={() => setDuration(m)}
                  >
                    {m}分
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="settings-card">
            <h2>2. 営業時間</h2>
            <p className="lead">定休にする曜日は「休み」をオンにしてください。</p>
            {hours.map((h, idx) => (
              <div className="hours-row" key={h.dow}>
                <div className="dow">{h.label}</div>
                <button
                  type="button"
                  className={`btn btn-ghost ${h.isClosed ? 'active' : ''}`}
                  onClick={() =>
                    setHours((prev) =>
                      prev.map((row, i) => (i === idx ? { ...row, isClosed: !row.isClosed } : row)),
                    )
                  }
                >
                  {h.isClosed ? '休み' : '営業'}
                </button>
                <input
                  type="time"
                  value={h.openTime || '11:00'}
                  disabled={h.isClosed}
                  onChange={(e) =>
                    setHours((prev) =>
                      prev.map((row, i) => (i === idx ? { ...row, openTime: e.target.value } : row)),
                    )
                  }
                />
                <input
                  type="time"
                  value={h.closeTime || '22:00'}
                  disabled={h.isClosed}
                  onChange={(e) =>
                    setHours((prev) =>
                      prev.map((row, i) => (i === idx ? { ...row, closeTime: e.target.value } : row)),
                    )
                  }
                />
              </div>
            ))}
          </section>

          <section className="settings-card">
            <h2>3. 席（AI予約枠）</h2>
            <p className="lead">初期はデモ店の席構成です。AIが使う卓だけが予約に使われます。</p>
            <div className="table-list">
              {(store?.tables || []).map((t) => (
                <div className="table-item" key={t.tableId}>
                  <div>
                    <strong>{t.label}</strong>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                      {t.capacity}名 / {t.tableId}
                    </div>
                  </div>
                  <span className={`badge ${t.aiBookable ? 'badge-phone' : 'badge-manual'}`}>
                    {t.aiBookable ? 'AI予約OK' : '当日客用'}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="settings-card">
            <h2>4. よくある質問</h2>
            <p className="lead">電話AIが答える内容です。分からないことは書かないでください。</p>
            {faqs.map((f, idx) => (
              <div className="faq-item" key={f.faqId || idx}>
                <div className="field">
                  <label>質問</label>
                  <input
                    value={f.question}
                    onChange={(e) =>
                      setFaqs((prev) =>
                        prev.map((row, i) => (i === idx ? { ...row, question: e.target.value } : row)),
                      )
                    }
                    placeholder="駐車場はありますか？"
                  />
                </div>
                <div className="field">
                  <label>答え</label>
                  <textarea
                    value={f.answer}
                    onChange={(e) =>
                      setFaqs((prev) =>
                        prev.map((row, i) => (i === idx ? { ...row, answer: e.target.value } : row)),
                      )
                    }
                    placeholder="近隣に有料コインパーキングがあります。"
                  />
                </div>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => setFaqs((prev) => prev.filter((_, i) => i !== idx))}
                >
                  この質問を削除
                </button>
              </div>
            ))}
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setFaqs((prev) => [...prev, emptyFaq(prev.length + 1)])}
            >
              ＋ FAQを追加
            </button>
          </section>
        </div>
      </div>
    </>
  )
}

function emptyFaq(n: number): StoreFaq {
  return {
    faqId: `f${String(n).padStart(3, '0')}`,
    question: '',
    answer: '',
    tags: [],
    enabled: true,
    sortOrder: n,
  }
}
