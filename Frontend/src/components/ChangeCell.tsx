import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface Props { value: number; showIcon?: boolean; className?: string }

export default function ChangeCell({ value, showIcon = true, className = '' }: Props) {
  const cls = value > 0 ? 'up' : value < 0 ? 'dn' : 'muted'
  const Icon = value > 0 ? TrendingUp : value < 0 ? TrendingDown : Minus
  return (
    <span className={`num flex items-center gap-1 ${cls} ${className}`}>
      {showIcon && <Icon size={12} />}
      {value > 0 ? '+' : ''}{value.toFixed(2)}%
    </span>
  )
}
