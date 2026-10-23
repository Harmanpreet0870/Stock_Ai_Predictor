interface Props {
  signal: string | null | undefined
  size?: 'xs' | 'sm' | 'md'
}

function normalize(raw: string): string {
  const s = raw.toUpperCase()
  if (s === 'STRONG BUY' || s.startsWith('BUY') || s.includes('_BUY')) return s.includes('STRONG') ? 'STRONG BUY' : 'BUY'
  if (s === 'STRONG SELL' || s.startsWith('SELL') || s.includes('_SELL')) return s.includes('STRONG') ? 'STRONG SELL' : 'SELL'
  if (s === 'BULL') return 'BULL'
  if (s === 'BEAR') return 'BEAR'
  if (s === 'NEUTRAL') return 'NEUTRAL'
  return 'HOLD'
}

export default function SignalBadge({ signal, size = 'sm' }: Props) {
  const raw = signal || 'HOLD'
  const n = normalize(raw)

  const map: Record<string, string> = {
    'STRONG BUY': 'tag-strong-buy',
    'BUY':        'tag-buy',
    'HOLD':       'tag-hold',
    'SELL':       'tag-sell',
    'STRONG SELL':'tag-strong-sell',
    'BULL':       'tag-bull',
    'BEAR':       'tag-bear',
    'NEUTRAL':    'tag-neutral',
  }

  const cls = map[n] ?? 'tag-neutral'
  const textSize = size === 'xs' ? 'text-[10px]' : size === 'sm' ? 'text-xs' : 'text-sm'

  return <span className={`${cls} ${textSize}`}>{n}</span>
}
