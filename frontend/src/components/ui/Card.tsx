// Author: 晨星
import type { ReactNode } from 'react'

type Props = {
  title?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}

export function Panel({ title, actions, children, className = '', bodyClassName = '' }: Props) {
  return (
    <section className={`flex min-h-0 flex-col rounded-lg border border-border bg-surface ${className}`}>
      {title ? (
        <header className="flex h-10 shrink-0 items-center justify-between border-b border-border px-3">
          <h2 className="text-[13px] font-medium tracking-wide text-fg-2">{title}</h2>
          <div className="flex items-center gap-1">{actions}</div>
        </header>
      ) : null}
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  )
}
