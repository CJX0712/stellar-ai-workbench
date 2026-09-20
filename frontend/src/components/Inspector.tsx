// Author: 晨星
import { useInspectorEntries, useInspectorTask, type InspectorKind } from '../lib/inspector'
import { Panel } from './ui/Card'

const sections: { kind: InspectorKind; label: string }[] = [
  { kind: 'context', label: 'Context · 上下文来源' },
  { kind: 'action', label: 'Action · 已执行动作' },
  { kind: 'observation', label: 'Observation · 执行日志' },
]

export function Inspector() {
  const entries = useInspectorEntries()
  const task = useInspectorTask()

  return (
    <aside className="hidden w-[320px] shrink-0 border-l border-border bg-surface lg:flex lg:flex-col">
      <Panel title="Inspector · 执行痕迹" className="h-full" bodyClassName="overflow-y-auto p-3">
        <div className="mb-3 rounded-md border border-border bg-surface-2 p-2.5">
          <div className="mb-1 text-[11px] uppercase tracking-wider text-muted">Task · 当前目标</div>
          <div className="text-[13px] leading-relaxed text-fg">{task || '尚无进行中的任务'}</div>
        </div>

        {sections.map((section) => {
          const items = entries.filter((entry) => entry.kind === section.kind)
          return (
            <div key={section.kind} className="mb-3 last:mb-0">
              <div className="mb-1.5 text-[11px] uppercase tracking-wider text-muted">{section.label}</div>
              {items.length === 0 ? (
                <div className="px-0.5 text-[12px] text-muted">暂无记录</div>
              ) : (
                <ul className="flex flex-col gap-1">
                  {items.slice(-12).map((entry) => (
                    <li
                      key={entry.id}
                      className="rounded-md border border-border bg-surface-2 px-2 py-1.5"
                    >
                      <div className="font-mono text-[10px] text-muted">{entry.at}</div>
                      <div className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-fg-2">
                        {entry.text}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </Panel>
    </aside>
  )
}
