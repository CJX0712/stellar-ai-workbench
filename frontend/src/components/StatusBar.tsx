// Author: 晨星
import { useTokenEstimate } from '../lib/usage'

type Props = {
  connected: boolean
  provider: string | null
}

export function StatusBar({ connected, provider }: Props) {
  const tokens = useTokenEstimate()
  return (
    <footer className="flex h-7 shrink-0 items-center gap-4 border-t border-border bg-surface px-3 text-[11px] text-muted">
      <span className="flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-success' : 'bg-danger'}`} />
        {connected ? '后端已连接' : '后端未连接'}
      </span>
      <span className="font-mono">provider: {provider ?? '—'}</span>
      <span className="font-mono">tokens≈{tokens}</span>
      <span className="ml-auto font-mono">Stellar AI Workbench · 晨星</span>
    </footer>
  )
}
