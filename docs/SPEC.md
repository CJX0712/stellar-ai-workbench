# Spec — Stellar AI Workbench v0.1.0

> 生成日期：2026-09-20
> 基于：PRD v0.1 + 架构文档 v0.1 + UIUX 文档 v0.1
> 状态：已确认
> 作者：晨星

---

## 1. 产品定义
- **一句话描述**：端到端可运行的模块化桌面 AI 工作台，整合开源成果，模块即插件、单一职责、可独立验证、干净环境一键复现。
- **目标用户**：独立开发者 / 技术创业者 / 中小团队技术负责人（Python+TS），要可复现、可署名、可自由切模型、避免厂商锁定的开源桌面 AI 平台。
- **核心问题**：现有 AI 桌面产品依赖易崩、厂商锁定、模块不可独立验证、无法一键复现。

## 2. MVP 范围（锁定）
| 优先级 | 功能 | 验收标准摘要 | RICE |
|--------|------|--------------|------|
| P0 | 统一模型网关（OpenAI 兼容 + 故障转移 + Mock） | 一行切厂商/模型，无 key 走 Mock 端到端跑通 | 高 |
| P0 | 模块化内核（9 模块单一职责 + 接口契约） | 每模块可独立单测 | 高 |
| P0 | 可插拔 RAG（文档导入 + 向量检索 + 增强回答） | 导入文档后检索增强可用 | 高 |
| P0 | 记忆/知识库（本地持久化） | 会话记忆 + 知识库落盘 | 高 |
| P0 | 干净环境一键复现（uv + pnpm 锁版 + 文档） | `uv sync`+`pnpm install` 起服务 | 高 |
| P0 | 桌面外壳（Tauri v2 + Python sidecar） | 配置完整，`tauri build` 出二进制 | 高 |
| P1 | 多智能体编排 | Agent.run 可组合工具/记忆 | 中 |
| P1 | 工具调用 / ToolRegistry | 注册并执行工具 | 中 |
| P1 | 助手与提示词管理 | 可保存/切换助手 | 中 |

## 3. 明确不做（Out-of-Scope）
| 不做 | 原因 | 何时考虑 |
|------|------|----------|
| 多用户/RBAC | MVP 单机优先 | v2.0 |
| 云端托管/SaaS | 定位桌面私有 | v2.0 |
| 图像生成 | 推理后端聚焦文本 | 后续 |
| 移动端 | 桌面优先 | 后续 |

## 4. 技术架构（锁定 — 版本锚定）
| 层 | 技术 | 版本 | 锁定原因 |
|----|------|------|----------|
| 桌面壳 | Tauri v2 | 2.11.x | sidecar 内嵌 Python，体积小 |
| 前端框架 | React | 19.x | 组件化、生态全 |
| 前端构建 | Vite | 7.x | 快、TS 原生 |
| 前端样式 | Tailwind CSS | 4.x | Token 驱动 |
| UI 组件 | shadcn/ui（Radix） | canary | 无障碍、可改 |
| 图标 | lucide-react (Lucide, MIT) | 0.4xx | 锁定一套 SVG，禁 emoji |
| 后端框架 | FastAPI | 0.115.x | 异步/OpenAPI |
| 推理接入 | openai (Py+TS) | py1.5x/ts4.x | OpenAI 兼容统一端点 |
| RAG | LlamaIndex | 0.11+ | 模块化检索 |
| 向量库 | LanceDB | 0.19x | 进程内、零运维 |
| 配置 | pydantic-settings | 2.x | env+文件 |
| 依赖锁 | uv / pnpm / Cargo | - | 确定性复现 |
| 认证 | 本地桌面无登录（BYOK） | - | 桌面私有 |

## 5. API 端点清单（锁定）
| Method | Path | 功能 | 认证 | 请求体 | 响应体 |
|--------|------|------|------|--------|--------|
| GET | /api/v1/health | 健康检查 | 无 | - | {status, modules[]} |
| GET | /api/v1/models | 列出可用模型 | 无 | - | {models[], active} |
| POST | /api/v1/chat | 对话（流式 SSE） | 无 | {messages, model?, stream?} | SSE: text/event-stream |
| POST | /api/v1/knowledge/add | 导入文档到知识库 | 无 | {kb_id, texts[]/file} | {chunk_count} |
| POST | /api/v1/rag/query | 检索增强问答 | 无 | {query, kb_id, top_k?} | {answer, sources[]} |
| POST | /api/v1/agents/run | 运行智能体任务 | 无 | {task, tools?, session?} | SSE: {step, observation} |
| POST | /api/v1/settings | 更新模型配置 | 无 | {base_url, api_key, model} | {ok} |

详见 `docs/openapi.yaml`。

## 6. 数据库表清单（锁定）
无传统 RDBMS。持久化采用：
| 存储 | 引擎 | 内容 | 路径 |
|------|------|------|------|
| 向量 | LanceDB | 知识块向量 + 原文 + 元数据 | `data/lancedb/` |
| 记忆/会话 | JSON 文件 | 会话历史、记忆条目 | `data/memory/<session>.json` |
| 配置 | env / `.env` | base_url/key/model | `.env`（不入库） |

## 7. 页面清单（锁定）
| 页面 | 路由 | 核心组件 | 对应 API | 设计主题 |
|------|------|----------|----------|----------|
| 聊天工作台 | / | ChatCanvas + Inspector + CommandBar | /chat,/rag/query | 深色精密仪器 |
| 知识库 | /knowledge | KnowledgeManager | /knowledge/add | 同上 |
| 智能体 | /agents | AgentRunner + ToolList | /agents/run | 同上 |
| 设置 | /settings | SettingsForm | /settings,/models | 同上 |

## 8. 设计 Token（锁定）
- 画布 `--bg:#0B0C0E`｜`--surface:#14161A`｜`--surface-2:#1C1F24`
- 文本 `--fg:#F2F4F7`｜`--fg-2:#C7CBD1`｜`--muted:#8A8F98`
- 边框 `--border:rgba(255,255,255,.07)`｜`--border-strong:rgba(255,255,255,.12)`
- 强调（唯一，每屏≤2处）`--accent:#22D3C5`
- 语义 `--success:#3FB950`｜`--warn:#E3A23C`｜`--danger:#F85149`
- 字体 Display/Body: Geist, Inter Variable, Noto Sans SC；Mono: JetBrains Mono
- 图标库：Lucide（MIT），尺寸 16/20/24px，描边 2px，currentColor
- 对标：Raycast×Linear×Open WebUI；三栏 + ⌘K 命令条 + Inspector(Task/Context/Action/Observation)
- **禁紫→粉渐变 / 禁 emoji 图标 / 禁硬编码颜色 / 禁占位文案 / 禁千篇一律 Hero**

## 9. 验收标准（EARS）
| 编号 | 功能 | EARS | 优先级 |
|------|------|------|--------|
| AC-01 | 健康检查 | When 请求 /health，系统必须返回 200 + 模块清单 | P0 |
| AC-02 | 对话 | While 用户发送消息，系统必须通过 OpenAI 兼容端点流式返回文本 | P0 |
| AC-03 | Mock 模式 | If 未配置 api_key，系统必须走 Mock Provider 返回可读响应，端到端可跑通 | P0 |
| AC-04 | 故障转移 | If 主模型 4xx/5xx，系统必须切换到 fallback 模型 | P0 |
| AC-05 | RAG | When 知识库已导入文档，系统必须对查询返回增强答案 + 来源 | P0 |
| AC-06 | 独立验证 | Each 模块必须拥有独立单元测试且全部通过 | P0 |
| AC-07 | 复现 | When 在干净环境执行 `uv sync`+`pnpm install`，系统必须可启动 | P0 |
| AC-08 | 智能体 | When 提交任务，系统必须按顺序执行工具并返回 Observation | P1 |

## 10. 边界与约束
- 桌面私有，无多用户；配置走 `.env`，不入库
- 响应式：桌面优先；窄屏右栏收抽屉
- 性能：首屏 < 3s；API p95 < 500ms（本地）
- 仅支持 OpenAI 兼容文本端点（MVP）

## 11. 内嵌已知坑
| 坑 | 指纹 | 根因 | 修法 |
|----|------|------|------|
| sidecar 跨平台 | tauri+python | sidecar 不能跨编译 | CI 分平台打包 PyInstaller |
| mock 验证 | 无 key 环境 | 强依赖外网 | 内置 MockProvider 离线跑通 |
| tailwind v4 | tailwindcss@4 | shadcn canary data-slot | 用 `@theme` + 标准 token |

## 12. 端到端验证步骤
```bash
# 1. 后端
cd backend && uv sync && uv run pytest -q        # 全绿（Mock 模式）
uv run uvicorn app.main:app --port 8000 &

# 2. 前端
cd ../frontend && pnpm install && pnpm build      # tsc + vite 成功

# 3. 核心成功流（Mock）
curl -N -X POST http://localhost:8000/api/v1/chat -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"你好"}],"model":"mock"}'
# 断言：SSE 流式返回文本

curl -X POST http://localhost:8000/api/v1/knowledge/add -H 'Content-Type: application/json' \
  -d '{"kb_id":"demo","texts":["Stellar 是晨星打造的模块化 AI 工作台"]}'
curl -X POST http://localhost:8000/api/v1/rag/query -H 'Content-Type: application/json' \
  -d '{"query":"Stellar 是什么","kb_id":"demo"}'
# 断言：返回增强答案 + 来源
```

## 13. 变更记录
| 日期 | 变更 | 原因 | 影响 |
|------|------|------|------|
| 2026-09-20 | 初始 Spec | 用户确认方案 | 全量 |
