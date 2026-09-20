// Author: 晨星
import { useEffect, useRef, useState } from 'react'
import { Send, Square, Terminal } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Textarea } from '../components/ui/Input'
import { chatStream, listModels, type ChatMessage, type ModelInfo } from '../lib/api'
import { inspector } from '../lib/inspector'
import { usage } from '../lib/usage'

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [model, setModel] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const result = await listModels()
        if (!alive) return
        setModels(result.models)
        if (!model) setModel(result.active)
      } catch {
        /* 后端未启动时保持空列表，状态条会显示未连接 */
      }
    }
    void load()
    return () => {
      alive = false
    }
  }, [model])

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    const userMessage: ChatMessage = { role: 'user', content: text }
    const history = [...messages, userMessage]

    setMessages([...history, { role: 'assistant', content: '' }])
    setStreaming(true)
    inspector.setTask(text)
    inspector.push('context', `上下文：${history.length} 条消息 / 模型 ${model || '默认'}`)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await chatStream(history, {
        model: model || undefined,
        onDelta: (delta) => {
          usage.add(delta.length)
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            next[next.length - 1] = { ...last, content: last.content + delta }
            return next
          })
        },
        signal: controller.signal,
      })
      inspector.push('action', `模型 ${model || '默认'} 已完成回复`)
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        next[next.length - 1] = { ...last, content: `${last.content}\n[请求失败] ${reason}` }
        return next
      })
      inspector.push('observation', `请求失败：${reason}`)
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const stop = () => {
    abortRef.current?.abort()
    setStreaming(false)
    inspector.push('observation', '用户中止了本次生成')
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2 text-[13px] text-fg-2">
          <Terminal size={16} strokeWidth={2} />
          聊天工作台
        </div>
        <select
          value={model}
          onChange={(event) => setModel(event.target.value)}
          className="h-8 rounded-md border border-border bg-surface-2 px-2 font-mono text-[12px] text-fg-2 outline-none"
        >
          {models.length === 0 ? <option value="">默认模型</option> : null}
          {models.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <p className="text-sm text-fg-2">开始一次对话，右侧 Inspector 会同步记录执行痕迹</p>
            <p className="text-[12px] text-muted">按 Ctrl K 打开命令面板 · 未配置密钥时自动走 Mock 模式</p>
          </div>
        ) : (
          <ul className="mx-auto flex max-w-3xl flex-col gap-3">
            {messages.map((message, index) => (
              <li key={index} className="flex flex-col gap-1">
                <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
                  {message.role === 'user' ? 'You' : 'Assistant'}
                </span>
                <div
                  className={[
                    'whitespace-pre-wrap break-words rounded-md px-3 py-2 text-[13px] leading-relaxed',
                    message.role === 'user'
                      ? 'border border-border bg-surface-2 text-fg'
                      : 'border border-border bg-surface text-fg',
                  ].join(' ')}
                >
                  {message.content || (streaming ? '生成中…' : '（空回复）')}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="shrink-0 border-t border-border p-3">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
            placeholder="输入消息，Enter 发送，Shift + Enter 换行"
            className="min-h-10"
          />
          {streaming ? (
            <Button variant="outline" onClick={stop}>
              <Square size={16} strokeWidth={2} />
              停止
            </Button>
          ) : (
            <Button variant="primary" onClick={() => void send()} disabled={input.trim().length === 0}>
              <Send size={16} strokeWidth={2} />
              发送
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
