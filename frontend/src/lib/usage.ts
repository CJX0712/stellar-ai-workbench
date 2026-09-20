// Author: 晨星
// 轻量用量统计：按字符数估算 token（约 4 字符/token），供状态条展示。
import { useSyncExternalStore } from 'react'

let chars = 0
const listeners = new Set<() => void>()

function emit(): void {
  for (const l of listeners) l()
}

export const usage = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  getChars(): number {
    return chars
  },
  add(count: number): void {
    chars += count
    emit()
  },
  reset(): void {
    chars = 0
    emit()
  },
}

export function useTokenEstimate(): number {
  const count = useSyncExternalStore(usage.subscribe, usage.getChars, usage.getChars)
  return Math.round(count / 4)
}
