import axios from 'axios'
import type {
  MarketOverview, MoversResponse, StockDetail, Candle,
  ScreenerResponse, Sector, SectorStock, PatternsResponse,
} from '../types'

const http = axios.create({ baseURL: '/api', timeout: 20000 })

export const api = {
  market: {
    overview: () => http.get<MarketOverview>('/market/overview').then(r => r.data),
    movers: (type: string, limit = 10) =>
      http.get<MoversResponse>('/market/movers', { params: { type, limit } }).then(r => r.data),
    dates: () => http.get<string[]>('/market/dates').then(r => r.data),
  },

  stocks: {
    search: (q: string) =>
      http.get<{ symbol: string }[]>('/stocks/search', { params: { q } }).then(r => r.data),
    detail: (symbol: string) =>
      http.get<StockDetail>(`/stocks/${symbol}`).then(r => r.data),
    history: (symbol: string, days = 120) =>
      http.get<Candle[]>(`/stocks/${symbol}/history`, { params: { days } }).then(r => r.data),
  },

  screener: (params: Record<string, unknown>) =>
    http.get<ScreenerResponse>('/screener', { params }).then(r => r.data),

  sectors: {
    list: () =>
      http.get<{ date: string; data: Sector[] }>('/sectors').then(r => r.data),
    stocks: (id: number) =>
      http
        .get<{ sector_id: number; sector_name: string; date: string; stocks: SectorStock[] }>(
          `/sectors/${id}/stocks`
        )
        .then(r => r.data),
  },

  patterns: (params: Record<string, unknown>) =>
    http.get<PatternsResponse>('/patterns', { params }).then(r => r.data),
}
