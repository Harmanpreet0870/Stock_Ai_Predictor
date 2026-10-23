interface Props { size?: 'sm' | 'md' | 'lg'; label?: string }

export default function LoadingSpinner({ size = 'md', label }: Props) {
  const s = { sm: 'h-5 w-5 border-2', md: 'h-9 w-9 border-2', lg: 'h-14 w-14 border-[3px]' }[size]
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <div className={`${s} animate-spin rounded-full border-surface-3 border-t-primary`} />
      {label && <p className="text-sm text-slate-500">{label}</p>}
    </div>
  )
}
