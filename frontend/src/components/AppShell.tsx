// Author: 晨星
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  BookOpen,
  Bot,
  MessageSquare,
  Plus,
  Search,
  Settings as SettingsIcon,
} from 'lucide-react'
import { Button } from './ui/Button'
import { Inspector } from './Inspector'
import { StatusBar } from './StatusBar'
import { CommandBar } from './CommandBar'
import { health, type Health } from '../lib/api'
import { inspector } from '../lib/inspector'

const navItems = [
  { to: '/', label: '聊天', icon: MessageSquare },
  { to: '/knowledge', label: '知识库', icon: BookOpen },
  { to: '/agents', label: '智能体', icon: Bot },
  { to: '/settings', label: '设置', icon: SettingsIcon },
]

export function AppShell() {
  const [commandOpen, setCommandOpen] = useState(false)
  const [status, setStatus] = useState<Health | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const result = await health()
        if (alive) setStatus(result)
      } catch {
        if (alive) setStatus(null)
      }
    }
    void load()
    const timer = window.setInterval(() => void load(), 15000)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[240px] shrink-0 flex-col border-r border-border bg-surface">
          <div className="flex h-12 items-center gap-2 border-b border-border px-3">
            <span className="text-sm font-semibold tracking-tight text-fg">Stellar</span>
            <span className="rounded-sm bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">
              v0.1.0
            </span>
          </div>

          <nav className="flex flex-col gap-0.5 p-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  [
                    'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors',
                    isActive ? 'bg-accent-soft text-accent' : 'text-fg-2 hover:bg-surface-2 hover:text-fg',
                  ].join(' ')
                }
              >
                <item.icon size={16} strokeWidth={2} />
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="mt-auto border-t border-border p-2">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                inspector.clear()
                navigate('/')
              }}
            >
              <Plus size={16} strokeWidth={2} />
              新建会话
            </Button>
            <button
              type="button"
              onClick={() => setCommandOpen(true)}
              className="mt-1.5 flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-[12px] text-muted transition-colors hover:bg-surface-2 hover:text-fg-2"
            >
              <Search size={16} strokeWidth={2} />
              命令面板
              <kbd className="ml-auto rounded-sm border border-border px-1 font-mono text-[10px]">Ctrl K</kbd>
            </button>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <Outlet />
        </main>

        <Inspector />
      </div>

      <StatusBar connected={status !== null} provider={status?.provider ?? null} />

      {commandOpen ? (
        <CommandBar
          onClose={() => setCommandOpen(false)}
          onNavigate={(to) => {
            navigate(to)
            setCommandOpen(false)
          }}
        />
      ) : null}
    </div>
  )
}
