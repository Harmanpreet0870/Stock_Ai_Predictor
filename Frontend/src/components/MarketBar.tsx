import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Minus, Zap } from 'lucide-react'
import { api } from '../api/client'
import type { MarketOverview } from '../types'

export default function MarketBar() {
  const [data, setData] = useState<MarketOverview | null>(null)

  useEffect(() => {
    api.market.overview().then(setData).catch(() => {})
  }, [])

  if (!data) return null

  return (
    <div className="bg-surface border-b border-rim px-4 py-2 overflow-x-auto">
      <div className="max-w-7xl mx-auto flex items-center gap-6 text-xs whitespace-nowrap">
        <span className="text-slate-500">{data.trading_date}</span>
        <div className="h-3 w-px bg-rim" />
        <Stat
          icon={<TrendingUp size={11} className="text-bullish" />}
          label="Advances"
          value={data.advances}
          cls="text-bullish"
        />
        <Stat
          icon={<TrendingDown size={11} className="text-bearish" />}
          label="Declines"
          value={data.declines}
          cls="text-bearish"
        />
        <Stat
          icon={<Minus size={11} className="text-slate-500" />}
          label="Unchanged"
          value={data.unchanged}
          cls="text-slate-400"
        />
        <div className="h-3 w-px bg-rim" />
        <Stat
          icon={<Zap size={11} className="text-bullish" />}
          label="Buy Signals"
          value={data.buy_signals}
          cls="text-bullish"
        />
        <Stat
          icon={<Zap size={11} className="text-bearish" />}
          label="Sell Signals"
          value={data.sell_signals}
          cls="text-bearish"
        />
        <div className="h-3 w-px bg-rim" />
        <span className="text-slate-500">
          AD Ratio: <span className={`num font-medium ${data.advance_decline_ratio >= 1 ? 'text-bullish' : 'text-bearish'}`}>
            {data.advance_decline_ratio}
          </span>
        </span>
      </div>
    </div>
  )
}

function Stat({ icon, label, value, cls }: { icon: React.ReactNode; label: string; value: number; cls: string }) {
  return (
    <div className="flex items-center gap-1">
      {icon}
      <span className="text-slate-500">{label}:</span>
      <span className={`num font-semibold ${cls}`}>{value.toLocaleString()}</span>
    </div>
  )
}
