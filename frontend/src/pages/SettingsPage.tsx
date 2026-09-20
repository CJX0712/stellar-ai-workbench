// Author: 晨星
import { useEffect, useState } from 'react'
import { Plug, Save } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Panel } from '../components/ui/Card'
import { getSettings, health, saveSettings, type Health } from '../lib/api'
import { inspector } from '../lib/inspector'

export function SettingsPage() {
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [fallback, setFallback] = useState('')
  const [hasKey, setHasKey] = useState(false)
  const [probe, setProbe] = useState<Health | null>(null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const result = await getSettings()
        if (!alive) return
        setBaseUrl(result.base_url ?? '')
        setModel(result.model ?? '')
        setFallback(result.fallback_model ?? '')
        setHasKey(result.has_api_key)
      } catch {
        if (alive) setNotice('读取配置失败，后端可能未启动')
      }
    }
    void load()
    return () => {
      alive = false
    }
  }, [])

  const onSave = async () => {
    try {
      await saveSettings({
        base_url: baseUrl || null,
        api_key: apiKey || null,
        model: model || null,
        fallback_model: fallback || null,
      })
      setNotice('配置已保存')
      inspector.push('action', '更新模型配置')
      setApiKey('')
      const refreshed = await getSettings()
      setHasKey(refreshed.has_api_key)
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      setNotice(`保存失败：${reason}`)
    }
  }

  const onProbe = async () => {
    try {
      const result = await health()
      setProbe(result)
      setNotice('连接正常')
      inspector.push('observation', `健康检查通过 provider=${result.provider}`)
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      setProbe(null)
      setNotice(`连接失败：${reason}`)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3">
      <Panel title="模型接入（OpenAI 兼容）" bodyClassName="flex flex-col gap-3 p-3">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-muted">Base URL</label>
            <Input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-muted">
              API Key {hasKey ? '（已配置，留空保持不变）' : '（未配置）'}
            </label>
            <Input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="sk-..."
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-muted">主模型</label>
            <Input value={model} onChange={(event) => setModel(event.target.value)} placeholder="gpt-4o-mini" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-muted">故障转移模型</label>
            <Input value={fallback} onChange={(event) => setFallback(event.target.value)} placeholder="mock" />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="primary" onClick={() => void onSave()}>
            <Save size={16} strokeWidth={2} />
            保存配置
          </Button>
          <Button variant="outline" onClick={() => void onProbe()}>
            <Plug size={16} strokeWidth={2} />
            测试连接
          </Button>
          {notice ? <span className="text-[12px] text-accent">{notice}</span> : null}
        </div>

        <p className="text-[12px] leading-relaxed text-muted">
          未填写 API Key 时，系统自动使用内置 Mock Provider，全链路仍可端到端跑通；主模型调用失败会切换到故障转移模型。
        </p>
      </Panel>

      <Panel title="后端状态" bodyClassName="p-3">
        {probe ? (
          <dl className="grid grid-cols-[120px_1fr] gap-y-1.5 text-[12px]">
            <dt className="text-muted">status</dt>
            <dd className="font-mono text-fg-2">{probe.status}</dd>
            <dt className="text-muted">provider</dt>
            <dd className="font-mono text-fg-2">{probe.provider}</dd>
            <dt className="text-muted">modules</dt>
            <dd className="font-mono text-fg-2">{probe.modules.join(', ')}</dd>
          </dl>
        ) : (
          <div className="text-[12px] text-muted">点击「测试连接」查看后端模块状态</div>
        )}
      </Panel>
    </div>
  )
}
