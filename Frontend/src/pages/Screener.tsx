import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Filter, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react'
import { api } from '../api/client'
import type { ScreenerResponse } from '../types'
import SignalBadge from '../components/SignalBadge'
import ChangeCell from '../components/ChangeCell'
import LoadingSpinner from '../components/LoadingSpinner'

interface Filters {
  signal: string
  supertrend: string
  min_rsi: string
  max_rsi: string
  min_change: string
  max_change: string
  bbs: string
  vt: string
  min_relvolume: string
  sort_by: string
  sort_order: string
}

const defaultFilters: Filters = {
  signal: '', supertrend: '', min_rsi: '', max_rsi: '',
  min_change: '', max_change: '', bbs: '', vt: '', min_relvolume: '',
  sort_by: 'perc_change', sort_order: 'desc',
}

export default function Screener() {
  const [data, setData] = useState<ScreenerResponse | null>(null)
  const [filters, setFilters] = useState<Filters>(defaultFilters)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [showFilters, setShowFilters] = useState(true)

  const fetch = useCallback(async (f: Filters, p: number) => {
    setLoading(true)
    const params: Record<string, unknown> = { page: p, limit: 50, sort_by: f.sort_by, sort_order: f.sort_order }
    if (f.signal) params.signal = f.signal
    if (f.supertrend) params.supertrend = Number(f.supertrend)
    if (f.min_rsi) params.min_rsi = Number(f.min_rsi)
    if (f.max_rsi) params.max_rsi = Number(f.max_rsi)
    if (f.min_change) params.min_change = Number(f.min_change)
    if (f.max_change) params.max_change = Number(f.max_change)
    if (f.bbs) params.bbs = f.bbs
    if (f.vt) params.vt = f.vt
    if (f.min_relvolume) params.min_relvolume = Number(f.min_relvolume)
    try {
      const res = await api.screener(params)
      setData(res)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetch(filters, page) }, [filters, page, fetch])

  const set = (k: keyof Filters, v: string) => { setPage(1); setFilters(f => ({ ...f, [k]: v })) }
  const reset = () => { setPage(1); setFilters(defaultFilters) }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 animate-fadeIn">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold">Stock Screener</h1>
          {data && (
            <p className="text-xs text-slate-500 mt-0.5">
              {data.total.toLocaleString()} results · {data.date}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={reset} className="btn-ghost flex items-center gap-1.5">
            <RotateCcw size={13} /> Reset
          </button>
          <button
            onClick={() => setShowFilters(v => !v)}
            className="btn-ghost flex items-center gap-1.5"
          >
            <Filter size={13} /> {showFilters ? 'Hide' : 'Show'} Filters
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="card mb-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          <FilterSelect label="Signal" value={filters.signal} onChange={v => set('signal', v)}
            options={[{ v: '', l: 'All Signals' }, { v: 'BUY', l: 'BUY' }, { v: 'SELL', l: 'SELL' }, { v: 'HOLD', l: 'HOLD' }]} />
          <FilterSelect label="SuperTrend" value={filters.supertrend} onChange={v => set('supertrend', v)}
            options={[{ v: '', l: 'All' }, { v: '1', l: 'Bullish ↑' }, { v: '-1', l: 'Bearish ↓' }]} />
          <FilterInput label="Min RSI" value={filters.min_rsi} onChange={v => set('min_rsi', v)} placeholder="e.g. 50" />
          <FilterInput label="Max RSI" value={filters.max_rsi} onChange={v => set('max_rsi', v)} placeholder="e.g. 70" />
          <FilterInput label="Min Change %" value={filters.min_change} onChange={v => set('min_change', v)} placeholder="e.g. 2" />
          <FilterInput label="Max Change %" value={filters.max_change} onChange={v => set('max_change', v)} placeholder="e.g. 10" />
          <FilterInput label="Min Rel. Volume" value={filters.min_relvolume} onChange={v => set('min_relvolume', v)} placeholder="e.g. 1.5" />
          <FilterSelect label="BB Signal" value={filters.bbs} onChange={v => set('bbs', v)}
            options={[{ v: '', l: 'All' }, { v: 'BULL', l: 'Bull' }, { v: 'BEAR', l: 'Bear' }, { v: 'NEUTRAL', l: 'Neutral' }]} />
          <FilterSelect label="VT Signal" value={filters.vt} onChange={v => set('vt', v)}
            options={[{ v: '', l: 'All' }, { v: 'BUY', l: 'BUY' }, { v: 'SELL', l: 'SELL' }, { v: 'HOLD', l: 'HOLD' }]} />
          <FilterSelect label="Sort By" value={filters.sort_by} onChange={v => set('sort_by', v)}
            options={[
              { v: 'perc_change', l: 'Change %' }, { v: 'rsi14', l: 'RSI 14' },
              { v: 'ema_strength', l: 'EMA Strength' }, { v: 'relvolume', l: 'Rel Volume' },
              { v: 'close_price', l: 'Price' },
            ]} />
          <FilterSelect label="Order" value={filters.sort_order} onChange={v => set('sort_order', v)}
            options={[{ v: 'desc', l: 'Descending' }, { v: 'asc', l: 'Ascending' }]} />
        </div>
      )}

      {loading ? (
        <LoadingSpinner label="Scanning stocks…" />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-rim">
            <table className="w-full text-sm">
              <thead className="bg-surface-2">
                <tr className="text-slate-500 text-xs">
                  {['Symbol', 'Price', 'Change %', 'Signal', 'RSI 14', 'EMA Str', 'RelVol', 'BB', 'VT', 'Candle', 'Deliv%'].map(h => (
                    <th key={h} className={`px-3 py-2.5 font-medium ${h === 'Symbol' ? 'text-left' : 'text-right'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data?.data.map(s => (
                  <tr key={s.symbol} className="border-t border-rim/40 hover:bg-surface-2 transition-colors">
                    <td className="px-3 py-2.5">
                      <Link to={`/stock/${s.symbol}`} className="font-mono font-semibold text-white hover:text-primary-light">
                        {s.symbol}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-right num">₹{s.close_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                    <td className="px-3 py-2.5 text-right"><ChangeCell value={s.perc_change} showIcon={false} /></td>
                    <td className="px-3 py-2.5 text-right"><SignalBadge signal={s.signal} /></td>
                    <td className={`px-3 py-2.5 text-right num ${s.rsi14 > 70 ? 'text-bearish' : s.rsi14 < 30 ? 'text-bullish' : 'text-slate-400'}`}>
                      {s.rsi14}
                    </td>
                    <td className={`px-3 py-2.5 text-right num text-xs ${s.ema_strength > 0 ? 'text-bullish' : 'text-bearish'}`}>
                      {s.ema_strength > 0 ? '+' : ''}{s.ema_strength.toFixed(2)}
                    </td>
                    <td className="px-3 py-2.5 text-right num text-slate-400 text-xs">{s.rel_volume}x</td>
                    <td className="px-3 py-2.5 text-right"><SignalBadge signal={s.bbs_signal} size="xs" /></td>
                    <td className="px-3 py-2.5 text-right"><SignalBadge signal={s.vt_signal} size="xs" /></td>
                    <td className="px-3 py-2.5 text-right text-xs text-slate-400">{s.candle_type.replace(/_/g, ' ')}</td>
                    <td className="px-3 py-2.5 text-right num text-xs text-slate-400">{s.deliv_per}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data && data.pages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-slate-500">
                Page {data.page} of {data.pages} · {data.total} results
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(p => p - 1)}
                  className="btn-ghost disabled:opacity-30 flex items-center gap-1"
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                <button
                  disabled={page >= data.pages}
                  onClick={() => setPage(p => p + 1)}
                  className="btn-ghost disabled:opacity-30 flex items-center gap-1"
                >
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

function FilterSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void
  options: { v: string; l: string }[]
}) {
  return (
    <div>
      <label className="text-xs text-slate-500 mb-1 block">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-surface-3 border border-rim rounded-lg px-2.5 py-1.5 text-sm
                   focus:outline-none focus:border-primary text-white"
      >
        {options.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </div>
  )
}

function FilterInput({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string
}) {
  return (
    <div>
      <label className="text-xs text-slate-500 mb-1 block">{label}</label>
      <input
        type="number"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-surface-3 border border-rim rounded-lg px-2.5 py-1.5 text-sm
                   focus:outline-none focus:border-primary placeholder-slate-600"
      />
    </div>
  )
}
