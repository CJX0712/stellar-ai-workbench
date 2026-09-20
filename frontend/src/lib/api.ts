// Author: 晨星
// 统一 API 客户端：REST + SSE 流式解析（对齐 docs/openapi.yaml）

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string }

export type Health = { status: string; provider: string; modules: string[] }
export type ModelInfo = { id: string; label: string; kind: string }
export type ModelsResp = { active: string; models: ModelInfo[] }
export type Source = { text: string; score: number; meta?: Record<string, unknown> | null }
export type RagResp = { answer: string; sources: Source[] }
export type SettingsResp = {
  base_url: string | null
  model: string
  has_api_key: boolean
  fallback_model: string | null
}
export type SaveSettingsBody = {
  base_url?: string | null
  api_key?: string | null
  model?: string | null
  fallback_model?: string | null
}
export type AgentStep = {
  type: string
  index: number
  thought?: string
  action?: string
  observation?: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${path} 失败：HTTP ${res.status}`)
  }
  return (await res.json()) as T
}

/**
 * 发起 SSE 请求并逐事件回调。后端以 `data: {json}\n\n` 形式推送。
 */
async function postSSE(
  path: string,
  body: unknown,
  onEvent: (evt: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) {
    throw new Error(`${path} 失败：HTTP ${res.status}`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload) continue
        try {
          onEvent(JSON.parse(payload) as Record<string, unknown>)
        } catch {
          onEvent({ type: 'raw', text: payload })
        }
      }
    }
  }
}

export const health = () => request<Health>('/api/v1/health')

export const listModels = () => request<ModelsResp>('/api/v1/models')

export const getSettings = () => request<SettingsResp>('/api/v1/settings')

export const saveSettings = (body: SaveSettingsBody) =>
  request<{ ok: boolean }>('/api/v1/settings', { method: 'POST', body: JSON.stringify(body) })

export const addKnowledge = (kbId: string, texts: string[]) =>
  request<{ kb_id: string; chunk_count: number }>('/api/v1/knowledge/add', {
    method: 'POST',
    body: JSON.stringify({ kb_id: kbId, texts }),
  })

export const ragQuery = (query: string, kbId: string, topK = 4, model?: string) =>
  request<RagResp>('/api/v1/rag/query', {
    method: 'POST',
    body: JSON.stringify({ query, kb_id: kbId, top_k: topK, model }),
  })

/** 对话流式：把每个 delta 追加回调出去 */
export async function chatStream(
  messages: ChatMessage[],
  opts: { model?: string; session?: string; onDelta: (text: string) => void; signal?: AbortSignal },
): Promise<void> {
  await postSSE(
    '/api/v1/chat',
    { messages, model: opts.model ?? null, session: opts.session ?? null, stream: true },
    (evt) => {
      if (evt.type === 'delta' && typeof evt.text === 'string') opts.onDelta(evt.text)
      if (evt.type === 'error' && typeof evt.message === 'string') opts.onDelta(`[错误] ${evt.message}`)
    },
    opts.signal,
  )
}

/** 智能体运行：逐步回调 Step */
export async function agentRun(
  task: string,
  opts: { session?: string; maxSteps?: number; onStep: (step: AgentStep) => void; signal?: AbortSignal },
): Promise<void> {
  await postSSE(
    '/api/v1/agents/run',
    { task, session: opts.session ?? null, max_steps: opts.maxSteps ?? 6 },
    (evt) => {
      opts.onStep({
        type: String(evt.type ?? 'step'),
        index: Number(evt.index ?? 0),
        thought: typeof evt.thought === 'string' ? evt.thought : undefined,
        action: typeof evt.action === 'string' ? evt.action : undefined,
        observation: typeof evt.observation === 'string' ? evt.observation : undefined,
      })
    },
    opts.signal,
  )
}
