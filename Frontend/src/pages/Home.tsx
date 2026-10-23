import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ArrowDownRight, Activity, BarChart2, Zap, ChevronRight } from 'lucide-react'
import { api } from '../api/client'
import type { MarketOverview, MoversResponse, PatternAlert } from '../types'
import SignalBadge from '../components/SignalBadge'
import ChangeCell from '../components/ChangeCell'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Home() {
  const [overview, setOverview] = useState<MarketOverview | null>(null)
  const [gainers, setGainers] = useState<MoversResponse | null>(null)
  const [losers, setLosers] = useState<MoversResponse | null>(null)
  const [buys, setBuys] = useState<MoversResponse | null>(null)
  const [patterns, setPatterns] = useState<PatternAlert[]>([])
  const [moverTab, setMoverTab] = useState<'gainers' | 'losers' | 'buysignals'>('gainers')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.market.overview(),
      api.market.movers('gainers', 12),
      api.market.movers('losers', 12),
      api.market.movers('buysignals', 12),
      api.patterns({ limit: 10, sentiment: 'bullish' }),
    ]).then(([ov, g, l, b, p]) => {
      setOverview(ov)
      setGainers(g)
      setLosers(l)
      setBuys(b)
      setPatterns(p.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner size="lg" label="Loading market data…" />

  const moverData = moverTab === 'gainers' ? gainers?.data : moverTab === 'losers' ? losers?.data : buys?.data

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6 animate-fadeIn">

      {/* ── Overview Stats ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Trading Date"
          value={overview?.trading_date ?? '—'}
          sub="Latest data"
          icon={<Activity size={16} className="text-primary-light" />}
          accent="blue"
        />
        <StatCard
          label="Advances / Declines"
          value={`${overview?.advances ?? 0} / ${overview?.declines ?? 0}`}
          sub={`AD Ratio: ${overview?.advance_decline_ratio ?? 0}`}
          icon={<ArrowUpRight size={16} className="text-bullish" />}
          accent={overview && overview.advances > overview.declines ? 'green' : 'red'}
        />
        <StatCard
          label="Buy Signals"
          value={overview?.buy_signals ?? 0}
          sub={`Sell: ${overview?.sell_signals ?? 0}`}
          icon={<Zap size={16} className="text-bullish" />}
          accent="green"
        />
        <StatCard
          label="SuperTrend Bullish"
          value={overview?.supertrend_bullish ?? 0}
          sub={`of ${overview?.total_symbols ?? 0} symbols`}
          icon={<BarChart2 size={16} className="text-primary-light" />}
          accent="blue"
        />
      </div>

      {/* ── Market Movers ── */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-sm text-slate-300">Market Movers</h2>
          <div className="flex gap-1">
            {(['gainers', 'losers', 'buysignals'] as const).map(t => (
              <button
                key={t}
                onClick={() => setMoverTab(t)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  moverTab === t ? 'bg-primary text-white' : 'text-slate-500 hover:text-white hover:bg-surface-2'
                }`}
              >
                {t === 'gainers' ? 'Top Gainers' : t === 'losers' ? 'Top Losers' : 'Buy Signals'}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-rim">
                <th className="text-left pb-2 font-medium">Symbol</th>
                <th className="text-right pb-2 font-medium">Price</th>
                <th className="text-right pb-2 font-medium">Change</th>
                <th className="text-right pb-2 font-medium hidden sm:table-cell">RSI</th>
                <th className="text-right pb-2 font-medium hidden md:table-cell">Rel Vol</th>
                <th className="text-center pb-2 font-medium">Signal</th>
              </tr>
            </thead>
            <tbody>
              {moverData?.map(s => (
                <tr key={s.symbol} className="border-b border-rim/40 hover:bg-surface-2 transition-colors">
                  <td className="py-2.5">
                    <Link
                      to={`/stock/${s.symbol}`}
                      className="font-mono font-semibold text-white hover:text-primary-light transition-colors"
                    >
                      {s.symbol}
                    </Link>
                  </td>
                  <td className="text-right num py-2.5">₹{s.close_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                  <td className="text-right py-2.5">
                    <ChangeCell value={s.perc_change} />
                  </td>
                  <td className="text-right num py-2.5 hidden sm:table-cell text-slate-400">{s.rsi14}</td>
                  <td className="text-right num py-2.5 hidden md:table-cell text-slate-400">{s.rel_volume}x</td>
                  <td className="text-center py-2.5"><SignalBadge signal={s.signal} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-right">
          <Link to="/screener" className="text-xs text-primary-light hover:underline flex items-center justify-end gap-1">
            Full Screener <ChevronRight size={12} />
          </Link>
        </div>
      </div>

      {/* ── Recent Pattern Alerts ── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-sm text-slate-300">Recent Pattern Alerts</h2>
          <Link to="/patterns" className="text-xs text-primary-light hover:underline flex items-center gap-1">
            View All <ChevronRight size={12} />
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {patterns.map((p, i) => <PatternMiniCard key={i} p={p} />)}
        </div>
      </div>
    </div>
  )
}

function StatCard({
  label, value, sub, icon, accent,
}: {
  label: string; value: string | number; sub: string; icon: React.ReactNode
  accent: 'green' | 'red' | 'blue'
}) {
  const borderCls = accent === 'green' ? 'border-bullish/20' : accent === 'red' ? 'border-bearish/20' : 'border-rim'
  return (
    <div className={`card border ${borderCls}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-500">{label}</span>
        {icon}
      </div>
      <div className="text-xl font-bold num">{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{sub}</div>
    </div>
  )
}

function PatternMiniCard({ p }: { p: PatternAlert }) {
  return (
    <Link to={`/stock/${p.symbol}`}>
      <div className={`card-sm hover:border-primary/40 transition-colors border ${
        p.sentiment === 'bullish' ? 'border-bullish/20' : 'border-bearish/20'
      }`}>
        <div className="flex items-start justify-between mb-1">
          <span className="font-mono font-bold text-sm text-white">{p.symbol}</span>
          <span className={`text-xs font-medium ${p.sentiment === 'bullish' ? 'text-bullish' : 'text-bearish'}`}>
            {p.sentiment === 'bullish' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          </span>
        </div>
        <div className="text-xs text-slate-400 mb-2">{p.pattern_type.replace(/_/g, ' ')}</div>
        <div className="grid grid-cols-3 gap-1 text-xs">
          <div><span className="muted">Entry</span><br /><span className="num text-white">₹{p.entry}</span></div>
          <div><span className="muted">SL</span><br /><span className="num text-bearish">₹{p.stop_loss}</span></div>
          <div><span className="muted">Target</span><br /><span className="num text-bullish">₹{p.target}</span></div>
        </div>
        {p.risk_reward > 0 && (
          <div className="mt-2 text-xs text-slate-500">R:R {p.risk_reward.toFixed(2)}</div>
        )}
      </div>
    </Link>
  )
}
