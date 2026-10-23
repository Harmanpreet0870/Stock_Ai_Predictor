import { useState, useEffect } from 'react'
import { ArrowUpRight, ArrowDownRight, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Sector, SectorStock } from '../types'
import SignalBadge from '../components/SignalBadge'
import ChangeCell from '../components/ChangeCell'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Sectors() {
  const [sectors, setSectors] = useState<Sector[]>([])
  const [date, setDate] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Sector | null>(null)
  const [sectorStocks, setSectorStocks] = useState<SectorStock[]>([])
  const [stocksLoading, setStocksLoading] = useState(false)

  useEffect(() => {
    api.sectors.list().then(r => {
      setSectors(r.data)
      setDate(r.date)
    }).finally(() => setLoading(false))
  }, [])

  const openSector = async (s: Sector) => {
    setSelected(s)
    setStocksLoading(true)
    const res = await api.sectors.stocks(s.id)
    setSectorStocks(res.stocks)
    setStocksLoading(false)
  }

  if (loading) return <LoadingSpinner size="lg" label="Loading sectors…" />

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 animate-fadeIn">
      <div className="mb-5">
        <h1 className="text-lg font-bold">Sector Overview</h1>
        <p className="text-xs text-slate-500 mt-0.5">{date} · {sectors.length} sectors</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {sectors.map(s => (
          <SectorCard key={s.id} sector={s} onClick={() => openSector(s)} />
        ))}
      </div>

      {/* Sector Stocks Drawer */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
          style={{ background: 'rgba(4,8,26,0.8)', backdropFilter: 'blur(4px)' }}>
          <div className="bg-surface-2 border border-rim rounded-2xl w-full max-w-3xl max-h-[80vh]
                          flex flex-col shadow-2xl animate-fadeIn">
            <div className="flex items-center justify-between px-5 py-4 border-b border-rim">
              <div>
                <h2 className="font-bold">{selected.display_name}</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {sectorStocks.length} stocks · Avg change: {selected.avg_change > 0 ? '+' : ''}{selected.avg_change}%
                </p>
              </div>
              <button onClick={() => setSelected(null)} className="text-slate-500 hover:text-white p-1">
                <X size={18} />
              </button>
            </div>
            <div className="overflow-auto flex-1">
              {stocksLoading ? (
                <LoadingSpinner label="Loading stocks…" />
              ) : (
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-2">
                    <tr className="text-slate-500 text-xs">
                      {['Symbol', 'Price', 'Change', 'Signal', 'RSI', 'RelVol', 'BB'].map(h => (
                        <th key={h} className={`px-4 py-2.5 font-medium ${h === 'Symbol' ? 'text-left' : 'text-right'}`}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sectorStocks.map(s => (
                      <tr key={s.symbol} className="border-t border-rim/40 hover:bg-surface-3 transition-colors">
                        <td className="px-4 py-2.5">
                          <Link
                            to={`/stock/${s.symbol}`}
                            onClick={() => setSelected(null)}
                            className="font-mono font-semibold text-white hover:text-primary-light"
                          >
                            {s.symbol}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 text-right num">₹{s.close_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                        <td className="px-4 py-2.5 text-right"><ChangeCell value={s.perc_change} showIcon={false} /></td>
                        <td className="px-4 py-2.5 text-right"><SignalBadge signal={s.signal} /></td>
                        <td className={`px-4 py-2.5 text-right num text-xs ${s.rsi14 > 70 ? 'text-bearish' : s.rsi14 < 30 ? 'text-bullish' : 'text-slate-400'}`}>
                          {s.rsi14}
                        </td>
                        <td className="px-4 py-2.5 text-right num text-xs text-slate-400">{s.rel_volume}x</td>
                        <td className="px-4 py-2.5 text-right"><SignalBadge signal={s.bbs_signal} size="xs" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SectorCard({ sector, onClick }: { sector: Sector; onClick: () => void }) {
  const pct = sector.stock_count > 0 ? (sector.advances / sector.stock_count) * 100 : 50
  const sentiment = pct > 55 ? 'bullish' : pct < 45 ? 'bearish' : 'neutral'
  const sentimentCls = sentiment === 'bullish' ? 'border-bullish/20' : sentiment === 'bearish' ? 'border-bearish/20' : 'border-rim'
  const avgCls = sector.avg_change >= 0 ? 'up' : 'dn'

  return (
    <button onClick={onClick} className={`card text-left hover:border-primary/40 transition-all border ${sentimentCls}`}>
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-sm leading-tight">{sector.display_name}</h3>
        <span className={`num text-sm font-bold flex-shrink-0 ml-2 ${avgCls}`}>
          {sector.avg_change > 0 ? '+' : ''}{sector.avg_change}%
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-500 mb-2">
        <span>{sector.stock_count} stocks</span>
        <span className="text-bullish flex items-center gap-0.5">
          <ArrowUpRight size={11} />{sector.advances}
        </span>
        <span className="text-bearish flex items-center gap-0.5">
          <ArrowDownRight size={11} />{sector.declines}
        </span>
      </div>
      <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${sentiment === 'bullish' ? 'bg-bullish' : sentiment === 'bearish' ? 'bg-bearish' : 'bg-hold'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-slate-600 mt-1">
        <span>{sector.advances} adv</span>
        <span>{sector.buy_count} buys</span>
        <span>{sector.declines} dec</span>
      </div>
    </button>
  )
}
