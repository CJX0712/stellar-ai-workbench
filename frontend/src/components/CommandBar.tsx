// Author: 晨星
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpen,
  Bot,
  CornerDownLeft,
  Eraser,
  MessageSquare,
  Plus,
  Settings as SettingsIcon,
  type LucideIcon,
} from 'lucide-react'
import { inspector } from '../lib/inspector'

type Command = {
  id: string
  label: string
  hint: string
  icon: LucideIcon
  run: () => void
}

type Props = {
  onClose: () => void
  onNavigate: (to: string) => void
}

export function CommandBar({ onClose, onNavigate }: Props) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const commands = useMemo<Command[]>(
    () => [
      {
        id: 'new-session',
        label: '新建会话',
        hint: '清空执行痕迹并重新计数',
        icon: Plus,
        run: () => {
          inspector.clear()
        },
      },
      { id: 'go-chat', label: '前往聊天工作台', hint: '/', icon: MessageSquare, run: () => onNavigate('/') },
      { id: 'go-knowledge', label: '前往知识库', hint: '/knowledge', icon: BookOpen, run: () => onNavigate('/knowledge') },
      { id: 'go-agents', label: '前往智能体', hint: '/agents', icon: Bot, run: () => onNavigate('/agents') },
      { id: 'go-settings', label: '前往设置', hint: '/settings', icon: SettingsIcon, run: () => onNavigate('/settings') },
      { id: 'clear-trace', label: '清空执行痕迹', hint: 'Inspector', icon: Eraser, run: () => inspector.clear() },
    ],
    [onNavigate],
  )

  const filtered = useMemo(
    () => commands.filter((c) => c.label.includes(query) || c.hint.includes(query)),
    [commands, query],
  )

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    setActive(0)
  }, [query])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setActive((i) => Math.min(i + 1, filtered.length - 1))
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setActive((i) => Math.max(i - 1, 0))
        return
      }
      if (event.key === 'Enter') {
        event.preventDefault()
        const target = filtered[active]
        if (target) {
          target.run()
          onClose()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [filtered, active, onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[12vh]"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-[560px] max-w-[92vw] overflow-hidden rounded-lg border border-border-strong bg-surface shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="输入命令，或按 Esc 关闭"
            className="h-11 w-full bg-transparent text-sm text-fg outline-none placeholder:text-muted"
          />
          <kbd className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted">Esc</kbd>
        </div>
        <ul className="max-h-72 overflow-y-auto p-1.5">
          {filtered.length === 0 ? (
            <li className="px-2.5 py-6 text-center text-[13px] text-muted">没有匹配的命令</li>
          ) : (
            filtered.map((command, index) => (
              <li key={command.id}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(index)}
                  onClick={() => {
                    command.run()
                    onClose()
                  }}
                  className={[
                    'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13px] transition-colors',
                    index === active ? 'bg-accent-soft text-accent' : 'text-fg-2 hover:bg-surface-2',
                  ].join(' ')}
                >
                  <command.icon size={16} strokeWidth={2} />
                  <span>{command.label}</span>
                  <span className="ml-auto font-mono text-[11px] text-muted">{command.hint}</span>
                  {index === active ? <CornerDownLeft size={14} strokeWidth={2} /> : null}
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  )
}
