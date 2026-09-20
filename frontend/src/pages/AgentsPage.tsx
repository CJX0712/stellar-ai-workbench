// Author: 晨星
import { useState } from 'react'
import { Play, Square } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Panel } from '../components/ui/Card'
import { agentRun, type AgentStep } from '../lib/api'
import { inspector } from '../lib/inspector'

export function AgentsPage() {
  const [task, setTask] = useState('')
  const [steps, setSteps] = useState<AgentStep[]>([])
  const [running, setRunning] = useState(false)

  const run = async () => {
    const goal = task.trim()
    if (!goal || running) return
    setSteps([])
    setRunning(true)
    inspector.clear()
    inspector.setTask(goal)
    inspector.push('context', `智能体会话启动 · 最多 6 步`)

    try {
      await agentRun(goal, {
        onStep: (step) => {
          setSteps((prev) => [...prev, step])
          if (step.thought) inspector.push('observation', step.thought)
          if (step.action) inspector.push('action', step.action)
          if (step.observation) inspector.push('observation', step.observation)
        },
      })
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      inspector.push('observation', `智能体运行失败：${reason}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-3">
      <Panel title="智能体任务" bodyClassName="flex flex-col gap-2 p-3">
        <div className="flex gap-2">
          <Input
            value={task}
            onChange={(event) => setTask(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void run()
            }}
            placeholder="描述一个目标，例如：检索知识库并总结要点"
          />
          {running ? (
            <Button variant="outline" onClick={() => setRunning(false)}>
              <Square size={16} strokeWidth={2} />
              停止
            </Button>
          ) : (
            <Button variant="primary" onClick={() => void run()} disabled={task.trim().length === 0}>
              <Play size={16} strokeWidth={2} />
              运行
            </Button>
          )}
        </div>
        <p className="text-[12px] text-muted">
          每一步的 Thought / Action / Observation 会实时同步到右侧 Inspector，可逐步审计。
        </p>
      </Panel>

      <Panel title="执行步骤" className="min-h-0 flex-1" bodyClassName="overflow-y-auto p-3">
        {steps.length === 0 ? (
          <div className="text-[12px] text-muted">尚未运行任务</div>
        ) : (
          <ol className="flex flex-col gap-2">
            {steps.map((step, index) => (
              <li key={`${step.index}-${index}`} className="rounded-md border border-border bg-surface-2 p-2.5">
                <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted">
                  step {step.index} · {step.type}
                </div>
                {step.thought ? (
                  <div className="text-[12px] leading-relaxed text-fg-2">
                    <span className="text-muted">Thought：</span>
                    {step.thought}
                  </div>
                ) : null}
                {step.action ? (
                  <div className="text-[12px] leading-relaxed text-fg-2">
                    <span className="text-muted">Action：</span>
                    {step.action}
                  </div>
                ) : null}
                {step.observation ? (
                  <div className="font-mono text-[12px] leading-relaxed text-accent">
                    <span className="text-muted">Observation：</span>
                    {step.observation}
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  )
}
