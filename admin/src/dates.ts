const WEEKDAYS = ['日', '月', '火', '水', '木', '金', '土']

export function todayInTokyo(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

export function shiftDate(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  dt.setUTCDate(dt.getUTCDate() + days)
  return dt.toISOString().slice(0, 10)
}

export function formatDateLabel(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  return `${m}/${d}（${WEEKDAYS[dt.getDay()]}）`
}

export function buildTimeChips(open = '11:00', close = '22:00', lastStart = '20:00', step = 30): string[] {
  const toMin = (hhmm: string) => {
    const [h, mi] = hhmm.split(':').map(Number)
    return h * 60 + mi
  }
  const start = toMin(open)
  const end = Math.min(toMin(close), toMin(lastStart))
  const out: string[] = []
  for (let t = start; t <= end; t += step) {
    out.push(`${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`)
  }
  return out
}
