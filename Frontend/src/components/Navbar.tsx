import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Search, TrendingUp, X, Menu } from 'lucide-react'
import { api } from '../api/client'

export default function Navbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<{ symbol: string }[]>([])
  const [open, setOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (query.trim().length < 1) { setResults([]); setOpen(false); return }
    const t = setTimeout(async () => {
      try {
        const data = await api.stocks.search(query.trim())
        setResults(data.slice(0, 8))
        setOpen(true)
      } catch { setResults([]) }
    }, 250)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const goTo = (sym: string) => {
    setQuery(''); setOpen(false)
    navigate(`/stock/${sym}`)
  }

  const navLinks = [
    { to: '/', label: 'Home' },
    { to: '/screener', label: 'Screener' },
    { to: '/sectors', label: 'Sectors' },
    { to: '/patterns', label: 'Patterns' },
  ]

  return (
    <nav className="sticky top-0 z-50 bg-surface/95 backdrop-blur border-b border-rim">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
            <TrendingUp size={15} className="text-white" />
          </div>
          <span className="font-bold text-sm tracking-tight hidden sm:block">
            Stock <span className="text-primary-light">AI</span> Predictor
          </span>
        </Link>

        {/* Desktop nav links */}
        <div className="hidden md:flex items-center gap-1 ml-2">
          {navLinks.map(l => (
            <Link
              key={l.to}
              to={l.to}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                location.pathname === l.to
                  ? 'bg-primary/20 text-primary-light font-medium'
                  : 'text-slate-400 hover:text-white hover:bg-surface-2'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>

        {/* Search */}
        <div ref={ref} className="relative flex-1 max-w-xs ml-auto">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={() => results.length && setOpen(true)}
            placeholder="Search symbol…"
            className="w-full bg-surface-2 border border-rim rounded-lg pl-8 pr-8 py-1.5
                       text-sm placeholder-slate-600 focus:outline-none focus:border-primary
                       transition-colors"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); setOpen(false) }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
            >
              <X size={12} />
            </button>
          )}
          {open && results.length > 0 && (
            <div className="absolute top-full mt-1 w-full bg-surface-2 border border-rim
                            rounded-lg shadow-2xl overflow-hidden z-50">
              {results.map(r => (
                <button
                  key={r.symbol}
                  onClick={() => goTo(r.symbol)}
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-surface-3
                             font-mono transition-colors flex items-center gap-2"
                >
                  <TrendingUp size={12} className="text-primary-light flex-shrink-0" />
                  {r.symbol}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Mobile menu toggle */}
        <button
          onClick={() => setMenuOpen(v => !v)}
          className="md:hidden text-slate-400 hover:text-white p-1"
        >
          <Menu size={18} />
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden border-t border-rim bg-surface px-4 pb-3">
          {navLinks.map(l => (
            <Link
              key={l.to}
              to={l.to}
              onClick={() => setMenuOpen(false)}
              className={`block py-2 text-sm ${
                location.pathname === l.to ? 'text-primary-light font-medium' : 'text-slate-400'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  )
}
