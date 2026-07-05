import { cn } from '@/lib/format'

interface Props {
  options: Array<{ value: string; label: string }>
  value: string
  onChange: (value: string) => void
  className?: string
}

export default function SegmentedControl({ options, value, onChange, className }: Props) {
  return (
    <div className={cn('neu-segment', className)}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={cn('neu-segment-item', value === opt.value && 'active')}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
