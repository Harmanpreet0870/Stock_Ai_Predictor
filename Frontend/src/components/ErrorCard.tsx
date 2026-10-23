import { AlertTriangle } from 'lucide-react'

interface Props { message?: string }

export default function ErrorCard({ message = 'Failed to load data' }: Props) {
  return (
    <div className="card flex items-center gap-3 text-bearish border-bearish/20">
      <AlertTriangle size={18} />
      <span className="text-sm">{message}</span>
    </div>
  )
}
