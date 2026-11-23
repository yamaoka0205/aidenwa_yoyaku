import { Link } from 'react-router-dom'

/**
 * gamen/doc/restaurant-ledger-ux-review.md の R1「タイムライン台帳」に寄せた製品モック。
 * 店内ストック写真は使わない（仕様でも写真背景はアンチパターン）。
 */
function LedgerScreen({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`mk-tl${compact ? ' is-compact' : ''}`} aria-hidden>
      <header className="mk-tl-head">
        <span className="mk-tl-home">⌂</span>
        <strong>デモ食堂さくら</strong>
        <div className="mk-tl-date">
          <span>‹</span>
          <em>11月21日（金）［今日］</em>
          <span>›</span>
        </div>
        <b className="mk-tl-plus">＋</b>
      </header>
      {!compact ? (
        <div className="mk-tl-summary">
          <span>
            予約 <b>4</b>組 / <b>15</b>名
          </span>
          <span>
            着席 <b>1</b>組
          </span>
          <span>
            未配席 <b>0</b>
          </span>
        </div>
      ) : null}
      <div className="mk-tl-body">
        <aside className="mk-tl-tables">
          <div className="mk-tl-tables-h">
            <span>卓</span>
            <span>定員</span>
          </div>
          <div className="mk-tl-trow is-wait">
            <i />
            <span>未配席</span>
            <em>1</em>
          </div>
          <div className="mk-tl-trow">
            <i className="c-teal" />
            <span>卓A</span>
            <em>4</em>
          </div>
          <div className="mk-tl-trow">
            <i className="c-red" />
            <span>卓B</span>
            <em>2</em>
          </div>
          <div className="mk-tl-trow">
            <i className="c-amber" />
            <span>卓C</span>
            <em>4</em>
          </div>
          {!compact ? (
            <div className="mk-tl-trow">
              <i className="c-blue" />
              <span>卓D</span>
              <em>6</em>
            </div>
          ) : null}
        </aside>
        <div className="mk-tl-grid">
          <div className="mk-tl-hours">
            <span>17:00</span>
            <span>18:00</span>
            <span className="is-now">18:02</span>
            <span>19:00</span>
            <span>20:00</span>
            {!compact ? <span>21:00</span> : null}
          </div>
          <div className="mk-tl-rows">
            <div className="mk-tl-row">
              <div className="mk-tl-bar is-open" style={{ left: '28%', width: '22%' }}>
                <b>2</b>
                <div>
                  <strong>山田</strong>
                  <small>電話 · 未配席</small>
                </div>
              </div>
            </div>
            <div className="mk-tl-row">
              <div className="mk-tl-bar is-booked" style={{ left: '18%', width: '34%' }}>
                <b>4</b>
                <div>
                  <strong>田中</strong>
                  <small>来店前 18:00</small>
                </div>
              </div>
            </div>
            <div className="mk-tl-row">
              <div className="mk-tl-bar is-seated" style={{ left: '26%', width: '30%' }}>
                <b>2</b>
                <div>
                  <strong>山田</strong>
                  <small>着席 0:28</small>
                </div>
              </div>
              <div className="mk-tl-buffer" style={{ left: '56%', width: '10%' }} />
            </div>
            <div className="mk-tl-row">
              <div className="mk-tl-bar is-booked" style={{ left: '42%', width: '28%' }}>
                <b>3</b>
                <div>
                  <strong>鈴木</strong>
                  <small>来店前 19:00</small>
                </div>
              </div>
            </div>
            {!compact ? (
              <div className="mk-tl-row">
                <div className="mk-tl-bar is-booked" style={{ left: '52%', width: '32%' }}>
                  <b>6</b>
                  <div>
                    <strong>佐藤</strong>
                    <small>来店前 19:45</small>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
          <div className="mk-tl-now" />
        </div>
      </div>
    </div>
  )
}

function PainVisual({ kind }: { kind: 'phone' | 'paper' | 'shift' }) {
  if (kind === 'phone') {
    return (
      <div className="mk-pain-visual" aria-hidden>
        <div className="mk-tl is-mini">
          <div className="mk-tl-row">
            <div className="mk-tl-bar is-open" style={{ left: '10%', width: '70%' }}>
              <b>2</b>
              <div>
                <strong>山田</strong>
                <small>電話 → 台帳へ</small>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }
  if (kind === 'paper') {
    return (
      <div className="mk-pain-visual is-paper" aria-hidden>
        <div className="mk-pain-sheet">
          <span>紙メモ 18:00 田中?</span>
          <span>Excel 行ずれ…</span>
        </div>
        <span className="mk-pain-arrow">→</span>
        <div className="mk-tl-bar is-booked is-inline">
          <b>4</b>
          <div>
            <strong>田中</strong>
            <small>同じ一覧</small>
          </div>
        </div>
      </div>
    )
  }
  return (
    <div className="mk-pain-visual is-shift" aria-hidden>
      <div className="mk-pain-shift-row">
        <em>昼番</em>
        <span>紙に書いて退勤</span>
      </div>
      <div className="mk-pain-shift-row is-night">
        <em>夜番</em>
        <span>開くと今夜のバーが一覧</span>
      </div>
    </div>
  )
}

export function LandingPage() {
  return (
    <div className="mk">
      <header className="mk-header">
        <div className="mk-header-inner">
          <Link to="/" className="mk-logo">
            よやく台帳
          </Link>
          <nav className="mk-nav">
            <a href="#problems">解決する課題</a>
            <a href="#features">機能</a>
            <a href="#pricing">料金</a>
            <a href="#flow">導入の流れ</a>
            <a href="#faq">よくある質問</a>
            <Link to="/login">ログイン</Link>
            <Link to="/apply" className="mk-cta">
              無料で申し込む
            </Link>
          </nav>
        </div>
      </header>

      <section className="mk-hero">
        <div className="mk-hero-inner">
          <div className="mk-hero-copy">
            <p className="mk-kicker">紙・Excel管理の小規模店から</p>
            <h1>
              電話の予約を、
              <br />
              台帳にそのまま。
            </h1>
            <p className="mk-pill">飲食店向け 予約・電話管理システム</p>
            <p className="mk-hero-lead">
              予約管理システム未導入の店舗向け。ピークの着信も、人数・時間・お名前をタイムライン台帳の一行に。紙と電話のあいだを、ひとつなぎにします。
            </p>
            <div className="mk-hero-actions">
              <Link to="/apply" className="mk-btn mk-btn-primary">
                無料で申し込む
              </Link>
              <a href="#pricing" className="mk-btn mk-btn-ghost">
                料金を見る
              </a>
            </div>
            <ul className="mk-hero-points">
              <li>初期費用 0円</li>
              <li>基本料 3,000円／月</li>
              <li>通話 50円／分</li>
            </ul>
          </div>
          <div className="mk-hero-visual">
            <div className="mk-device is-hero">
              <LedgerScreen />
            </div>
          </div>
        </div>
      </section>

      <section className="mk-trust" aria-label="できること">
        <div className="mk-wrap mk-trust-inner">
          <span>電話予約の取り込み</span>
          <span>手入力と同じ一覧</span>
          <span>今夜の席が一目</span>
          <span>承認制で安心して開始</span>
        </div>
      </section>

      <section className="mk-section" id="problems">
        <div className="mk-wrap">
          <h2 className="mk-h2">
            こんなお悩みを
            <br />
            <em>よやく台帳</em>が解決します
          </h2>
          <div className="mk-pain-grid">
            <article className="mk-pain">
              <PainVisual kind="phone" />
              <div className="mk-pain-body">
                <p className="mk-pain-q">ピークの電話でホールが手薄</p>
                <p className="mk-pain-a">着信内容を台帳へそのまま残せます</p>
              </div>
            </article>
            <article className="mk-pain">
              <PainVisual kind="paper" />
              <div className="mk-pain-body">
                <p className="mk-pain-q">紙・Excelの転記ミス</p>
                <p className="mk-pain-a">電話も手入力も同じ一覧で管理</p>
              </div>
            </article>
            <article className="mk-pain">
              <PainVisual kind="shift" />
              <div className="mk-pain-body">
                <p className="mk-pain-q">シフト交代で席が引き継がれない</p>
                <p className="mk-pain-a">開いた瞬間、今夜の予約がわかる</p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="mk-band" id="features">
        <div className="mk-wrap">
          <p className="mk-band-eyebrow">豊富な機能</p>
          <h2 className="mk-h2 is-light">現場が迷わない、今夜の台帳</h2>
          <div className="mk-feature-blocks">
            <article className="mk-feature-block">
              <div className="mk-feature-copy">
                <h3>タイムラインで今夜の席が一目</h3>
                <p>
                  卓×時間のグリッドに予約バーを並べます。時刻・人数・名前がバー上で読めるので、紙台帳から移っても迷いません。
                </p>
                <ul>
                  <li>左に卓名と定員、右に時間軸</li>
                  <li>来店前／着席を塗り分け</li>
                  <li>電話予約も同じバーで表示</li>
                </ul>
              </div>
              <div className="mk-device">
                <LedgerScreen />
              </div>
            </article>
            <article className="mk-feature-block is-reverse">
              <div className="mk-feature-copy">
                <h3>電話対応の負荷を下げる</h3>
                <p>
                  ピーク時でも着信内容を聞き逃さず台帳へ残せます。ホール接客に集中できる時間をつくります。
                </p>
                <ul>
                  <li>電話予約の取り込み</li>
                  <li>転記作業の削減</li>
                  <li>二重予約リスクの低減</li>
                </ul>
              </div>
              <div className="mk-device is-feature-side">
                <LedgerScreen compact />
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="mk-voice">
        <div className="mk-wrap mk-voice-inner">
          <div className="mk-voice-ui" aria-hidden>
            <LedgerScreen compact />
          </div>
          <blockquote>
            <p>
              紙台帳と電話メモが別管理で、ピークのたびに確認が追いつかなかった。一覧が一つになると、交代の引き継ぎが楽になった。
            </p>
            <cite>飲食店オーナー（導入イメージ）</cite>
          </blockquote>
        </div>
      </section>

      <section className="mk-section" id="pricing">
        <div className="mk-wrap">
          <h2 className="mk-h2">料金</h2>
          <p className="mk-section-lead">
            台帳利用の基本料に加え、電話応対の通話時間だけ従量課金します。初期費用はありません。
          </p>
          <div className="mk-price-grid">
            <article className="mk-price">
              <p className="mk-price-label">基本利用料</p>
              <p className="mk-price-amount">
                <strong>3,000</strong>
                <span>円／月（税別）</span>
              </p>
              <ul>
                <li>予約台帳・手入力予約</li>
                <li>店舗設定（席・営業時間）</li>
                <li>電話予約の一覧表示</li>
              </ul>
            </article>
            <article className="mk-price is-accent">
              <p className="mk-price-label">通話課金</p>
              <p className="mk-price-amount">
                <strong>50</strong>
                <span>円／分（税別）</span>
              </p>
              <ul>
                <li>電話応対の通話時間</li>
                <li>1分未満は1分として計算</li>
                <li>通話のない月は発生しません</li>
              </ul>
            </article>
          </div>
          <p className="mk-price-note">
            例）月の通話が合計40分の場合：基本料3,000円 + 通話2,000円 = 5,000円（税別）
          </p>
        </div>
      </section>

      <section className="mk-section mk-section-soft" id="flow">
        <div className="mk-wrap">
          <h2 className="mk-h2">導入までのステップ</h2>
          <ol className="mk-steps">
            <li>
              <span className="mk-step-num">STEP 1</span>
              <strong>フォーム入力</strong>
              <p>店舗名・担当者・メールを送信。申し込み時のカード登録は不要です。</p>
            </li>
            <li>
              <span className="mk-step-num">STEP 2</span>
              <strong>運営者の承認</strong>
              <p>内容を確認後、アカウントを発行します。</p>
            </li>
            <li>
              <span className="mk-step-num">STEP 3</span>
              <strong>利用開始</strong>
              <p>登録メールでログインし、台帳を使い始められます。</p>
            </li>
          </ol>
        </div>
      </section>

      <section className="mk-section" id="faq">
        <div className="mk-wrap mk-faq-wrap">
          <h2 className="mk-h2">よくある質問</h2>
          <details className="mk-faq" open>
            <summary>申し込み後、すぐに使えますか？</summary>
            <p>運営者の承認後、登録メールでログインできます。承認は内容確認後に行います。</p>
          </details>
          <details className="mk-faq">
            <summary>料金はどうなりますか？</summary>
            <p>
              基本利用料3,000円／月（税別）に加え、電話応対の通話は50円／分（税別）です。初期費用はありません。
            </p>
          </details>
          <details className="mk-faq">
            <summary>申し込み時にクレジットカードは必要ですか？</summary>
            <p>不要です。カード登録なしで申し込めます。請求方法は利用開始時にご案内します。</p>
          </details>
          <details className="mk-faq">
            <summary>電話予約と手入力は別画面ですか？</summary>
            <p>同じ台帳一覧に並びます。電話経由は「電話」バッジで判別できます。</p>
          </details>
        </div>
      </section>

      <section className="mk-cta-band">
        <div className="mk-wrap mk-cta-inner">
          <h2>まずは店舗を申し込む</h2>
          <p>承認後、登録メールでログインできます。基本料3,000円／月＋通話50円／分（税別）。</p>
          <Link to="/apply" className="mk-btn mk-btn-primary">
            無料で申し込む
          </Link>
        </div>
      </section>

      <aside className="mk-float-cta" aria-label="申し込み">
        <p>初期費用0円</p>
        <Link to="/apply">申し込む</Link>
      </aside>

      <footer className="mk-footer">
        <div className="mk-wrap mk-footer-inner">
          <span>よやく台帳</span>
          <div>
            <Link to="/login">店舗ログイン</Link>
            <Link to="/operator/login">運営</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
