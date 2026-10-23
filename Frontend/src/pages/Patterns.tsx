import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ArrowDownRight, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import { api } from '../api/client'
import type { PatternsResponse } from '../types'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Patterns() {
  const [data, setData] = useState<PatternsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [sentiment, setSentiment] = useState('')
  const [patternType, setPatternType] = useState('')
  const [symbol, setSymbol] = useState('')
  const [page, setPage] = useState(1)

  const fetch = useCallback(async (p: number, s: string, pt: string, sym: string) => {
    setLoading(true)
    const params: Record<string, unknown> = { page: p, limit: 50 }
    if (s) params.sentiment = s
    if (pt) params.pattern_type = pt
    if (sym) params.symbol = sym.toUpperCase()
    try {
      const res = await api.patterns(params)
      setData(res)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetch(page, sentiment, patternType, symbol) }, [page, sentiment, patternType, symbol, fetch])

  const reset = () => { setPage(1); setSentiment(''); setPatternType(''); setSymbol('') }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 animate-fadeIn">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold">Pattern Alerts</h1>
          {data && (
            <p className="text-xs text-slate-500 mt-0.5">{data.total.toLocaleString()} patterns detected</p>
          )}
        </div>
        <button onClick={reset} className="btn-ghost flex items-center gap-1.5">
          <RotateCcw size={13} /> Reset
        </button>
      </div>

      {/* Filters */}
      <div className="card mb-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Sentiment</label>
          <select
            value={sentiment}
            onChange={e => { setSentiment(e.target.value); setPage(1) }}
            className="bg-surface-3 border border-rim rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary"
          >
            <option value="">All</option>
            <option value="bullish">Bullish</option>
            <option value="bearish">Bearish</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Pattern Type</label>
          <select
            value={patternType}
            onChange={e => { setPatternType(e.target.value); setPage(1) }}
            className="bg-surface-3 border border-rim rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary"
          >
            <option value="">All Patterns</option>
            {data?.pattern_types.map(t => (
              <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 mb-1 block">Symbol</label>
          <input
            value={symbol}
            onChange={e => { setSymbol(e.target.value); setPage(1) }}
            placeholder="e.g. RELIANCE"
            className="bg-surface-3 border border-rim rounded-lg px-3 py-1.5 text-sm w-32
                       focus:outline-none focus:border-primary placeholder-slate-600 uppercase font-mono"
          />
        </div>
      </div>

      {loading ? <LoadingSpinner label="Loading patterns…" /> : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data?.data.map((p, i) => (
              <div key={i} className={`card border hover:border-primary/30 transition-colors ${
                p.sentiment === 'bullish' ? 'border-bullish/15' : 'border-bearish/15'
              }`}>
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <Link
                      to={`/stock/${p.symbol}`}
                      className="font-mono font-bold text-white hover:text-primary-light transition-colors"
                    >
                      {p.symbol}
                    </Link>
                    <p className="text-xs text-slate-500 mt-0.5">{p.trade_date}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {p.sentiment === 'bullish'
                      ? <ArrowUpRight size={16} className="text-bullish" />
                      : <ArrowDownRight size={16} className="text-bearish" />
                    }
                    <span className={`text-xs font-semibold ${p.sentiment === 'bullish' ? 'text-bullish' : 'text-bearish'}`}>
                      {p.signal}
                    </span>
                  </div>
                </div>

                <div className="text-xs font-medium text-slate-300 mb-3 bg-surface-3 rounded px-2 py-1 inline-block">
                  {p.pattern_type.replace(/_/g, ' ')}
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-surface-3 rounded-lg p-2">
                    <div className="text-slate-500 mb-0.5">Entry</div>
                    <div className="num font-semibold text-white">₹{p.entry}</div>
                  </div>
                  <div className="bg-surface-3 rounded-lg p-2">
                    <div className="text-slate-500 mb-0.5">Stop Loss</div>
                    <div className="num font-semibold text-bearish">₹{p.stop_loss}</div>
                  </div>
                  <div className="bg-surface-3 rounded-lg p-2">
                    <div className="text-slate-500 mb-0.5">Target</div>
                    <div className="num font-semibold text-bullish">₹{p.target}</div>
                  </div>
                </div>

                <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
                  <span>R:R {p.risk_reward.toFixed(2)}</span>
                  <span>Risk {p.risk_pct}%</span>
                  {p.score != null && <span>Score {p.score.toFixed(0)}</span>}
                </div>
              </div>
            ))}
          </div>

          {data && data.pages > 1 && (
            <div className="flex items-center justify-between mt-5">
              <span className="text-xs text-slate-500">Page {data.page} of {data.pages}</span>
              <div className="flex gap-2">
                <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                  className="btn-ghost disabled:opacity-30 flex items-center gap-1">
                  <ChevronLeft size={14} /> Prev
                </button>
                <button disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}
                  className="btn-ghost disabled:opacity-30 flex items-center gap-1">
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
