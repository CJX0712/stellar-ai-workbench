// Author: 晨星
import { useState } from 'react'
import { FilePlus2, Search } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input, Textarea } from '../components/ui/Input'
import { Panel } from '../components/ui/Card'
import { addKnowledge, ragQuery, type Source } from '../lib/api'
import { inspector } from '../lib/inspector'

export function KnowledgePage() {
  const [kbId, setKbId] = useState('default')
  const [docs, setDocs] = useState('')
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState<Source[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  const onImport = async () => {
    const texts = docs
      .split(/\n{2,}/)
      .map((part) => part.trim())
      .filter(Boolean)
    if (texts.length === 0) return
    setBusy(true)
    try {
      const result = await addKnowledge(kbId, texts)
      setNotice(`已写入知识库 ${result.kb_id}，新增 ${result.chunk_count} 个片段`)
      inspector.setTask(`导入 ${texts.length} 段文本到知识库 ${kbId}`)
      inspector.push('context', `知识库 ${kbId} · 本次导入 ${result.chunk_count} 个片段`)
      inspector.push('action', 'knowledge/add 写入成功')
      setDocs('')
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      setNotice(`导入失败：${reason}`)
      inspector.push('observation', `导入失败：${reason}`)
    } finally {
      setBusy(false)
    }
  }

  const onQuery = async () => {
    if (!query.trim()) return
    setBusy(true)
    try {
      const result = await ragQuery(query.trim(), kbId)
      setAnswer(result.answer)
      setSources(result.sources)
      inspector.setTask(`检索问答：${query.trim()}`)
      inspector.push('context', `命中 ${result.sources.length} 个来源片段（知识库 ${kbId}）`)
      inspector.push('observation', result.answer.slice(0, 200))
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      setAnswer(`检索失败：${reason}`)
      inspector.push('observation', `检索失败：${reason}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-0 flex-1 gap-3 overflow-y-auto p-3 lg:grid-cols-2">
      <Panel title="导入知识" bodyClassName="flex flex-col gap-2 p-3">
        <label className="text-[11px] uppercase tracking-wider text-muted">知识库 ID</label>
        <Input value={kbId} onChange={(event) => setKbId(event.target.value)} placeholder="default" />

        <label className="mt-1 text-[11px] uppercase tracking-wider text-muted">文档内容（空行分段）</label>
        <Textarea
          value={docs}
          onChange={(event) => setDocs(event.target.value)}
          placeholder="粘贴文档正文，两个换行视为一个新片段"
          className="min-h-40 flex-1"
        />

        <Button variant="primary" onClick={() => void onImport()} disabled={busy || docs.trim().length === 0}>
          <FilePlus2 size={16} strokeWidth={2} />
          导入到知识库
        </Button>
      </Panel>

      <Panel title="检索增强问答" bodyClassName="flex min-h-0 flex-col gap-2 p-3">
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void onQuery()
            }}
            placeholder="对知识库提问，例如：这份文档讲了什么"
          />
          <Button variant="primary" onClick={() => void onQuery()} disabled={busy || query.trim().length === 0}>
            <Search size={16} strokeWidth={2} />
            检索
          </Button>
        </div>

        {notice ? <div className="text-[12px] text-accent">{notice}</div> : null}

        <div className="min-h-0 flex-1 overflow-y-auto rounded-md border border-border bg-surface-2 p-2.5">
          <div className="mb-1 text-[11px] uppercase tracking-wider text-muted">Answer · 增强答案</div>
          <div className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-fg">
            {answer || '尚未发起检索'}
          </div>
        </div>

        <div className="max-h-56 overflow-y-auto rounded-md border border-border bg-surface-2 p-2.5">
          <div className="mb-1 text-[11px] uppercase tracking-wider text-muted">Sources · 命中来源</div>
          {sources.length === 0 ? (
            <div className="text-[12px] text-muted">暂无来源</div>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {sources.map((source, index) => (
                <li key={index} className="rounded-md border border-border bg-surface px-2 py-1.5">
                  <div className="font-mono text-[10px] text-muted">score {source.score.toFixed(4)}</div>
                  <div className="text-[12px] leading-relaxed text-fg-2">{source.text}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Panel>
    </div>
  )
}
