import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import MarketBar from './components/MarketBar'
import Home from './pages/Home'
import Screener from './pages/Screener'
import StockDetail from './pages/StockDetail'
import Sectors from './pages/Sectors'
import Patterns from './pages/Patterns'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-bg text-white">
        <Navbar />
        <MarketBar />
        <main className="pb-12">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
            <Route path="/sectors" element={<Sectors />} />
            <Route path="/patterns" element={<Patterns />} />
          </Routes>
        </main>
        <footer className="text-center text-xs text-slate-700 py-4 border-t border-rim">
          Stock AI Predictor · Data from NSE India · For educational purposes only
        </footer>
      </div>
    </BrowserRouter>
  )
}
