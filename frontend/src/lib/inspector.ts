// Author: 晨星
// Inspector 轻量状态仓：Task / Context / Action / Observation 四类执行痕迹，
// 供右侧 Inspector 面板订阅，全局可审计。
import { useSyncExternalStore } from 'react'

export type InspectorKind = 'task' | 'context' | 'action' | 'observation'

export type InspectorEntry = {
  id: string
  kind: InspectorKind
  text: string
  at: string
}

let entries: InspectorEntry[] = []
let task = ''
const listeners = new Set<() => void>()

function emit(): void {
  for (const l of listeners) l()
}

function now(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

export const inspector = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  getSnapshot(): InspectorEntry[] {
    return entries
  },
  getTask(): string {
    return task
  },
  setTask(next: string): void {
    task = next
    emit()
  },
  push(kind: InspectorKind, text: string): void {
    const entry: InspectorEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      kind,
      text,
      at: now(),
    }
    entries = [...entries, entry].slice(-200)
    emit()
  },
  clear(): void {
    entries = []
    task = ''
    emit()
  },
}

export function useInspectorEntries(): InspectorEntry[] {
  return useSyncExternalStore(inspector.subscribe, inspector.getSnapshot, inspector.getSnapshot)
}

export function useInspectorTask(): string {
  return useSyncExternalStore(inspector.subscribe, inspector.getTask, inspector.getTask)
}
