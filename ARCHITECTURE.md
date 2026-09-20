# 架构说明 · Stellar AI Workbench

> 作者：晨星 · 配套文档：`docs/SPEC.md`（规格契约）、`docs/openapi.yaml`（接口契约）、`docs/decisions/`

本文说明系统的**设计取舍、运行时链路与扩展方式**，供二次开发与评审使用。

---

## 1. 设计原则

| 原则 | 落地方式 |
|------|----------|
| 单一职责 | 每个模块一个目录文件，只做一件事；`main.py` 仅装配、零业务逻辑 |
| 依赖倒置 | 模块只依赖 `Protocol`（`Provider` / `VectorStore` / `Embedder`），实现运行时注入 |
| 契约优先 | 先有 `docs/SPEC.md` 与 `openapi.yaml`，前后端分别据此实现与生成类型 |
| 可独立验证 | 任何模块可在无网络、无真实模型、无真实向量库的条件下单测 |
| 可复现 | 依赖版本全锁（requirements / package-lock / Cargo.lock），单一安装入口 |
| 失败可降级 | 推理与向量两层均有明确的降级链，且降级对上层透明 |

---

## 2. 运行时数据流

### 2.1 对话（`POST /api/v1/chat`）

```
UI 输入
  └─▶ routes_chat 校验 → InferenceProxy.astream(messages, model)
        └─▶ _plan(model) 展开降级链 → 逐个 Provider 尝试
              └─▶ 首个成功的 Provider 逐个 chunk 产出文本
                    └─▶ sse.py 打包为 `data: {"type":"delta","text":...}`
                          └─▶ 前端 ReadableStream 解析并追加到气泡
```

### 2.2 检索增强问答（`POST /api/v1/rag/query`）

```
query
  └─▶ RAGPipeline.answer(query, kb_id, top_k)
        ├─▶ InferenceProxy.embed([query]) → 查询向量
        ├─▶ Retrieval.query(kb_id, vec, top_k) → Hit[]（text/score/meta）
        ├─▶ build_context(hits) 组装带编号的上下文
        ├─▶ InferenceProxy.chat(prompt)
        └─▶ 返回 { answer, sources[] }
```

### 2.3 智能体（`POST /api/v1/agents/run`）

```
task
  └─▶ Agent.run(task, session, max_steps)   # 自研 ReAct 循环
        重复至多 max_steps 次：
          ├─▶ think：调推理，产出「用哪个工具 + 参数」
          ├─▶ act：ToolRegistry.execute(name, args)
          ├─▶ observe：记录结果，作为 SSE step 推给前端
          └─▶ 决策为 final 时终止
        └─▶ MemoryStore.store(session, turn)  # 会话记忆落盘
```

---

## 3. 降级链（失败透明化）

**推理层**：`主模型 → FALLBACK_MODEL → MockProvider`，链尾恒为 Mock，保证系统永远能应答。
当前生效的 provider 由 `GET /api/v1/health` 的 `provider` 字段暴露，避免"静默降级掩盖真实故障"。

**向量层**：`VECTOR_BACKEND=auto` 时优先 LanceDB；导入/依赖不可用时记录告警并回退 `NumpyVectorStore`，
两者实现同一 `VectorStore` 协议，上层无感。可用 `VECTOR_BACKEND=lancedb` 强制并要求显式失败。

> 设计动机：Mock 不是"演示玩具"，而是**干净环境可验证性**的硬要求——CI 与离线环境必须能跑通完整链路。

---

## 4. 扩展点

| 想扩展 | 做法 |
|--------|------|
| 接入新厂商 | 实现一个满足 `Provider` 协议的类（`chat` / `astream` / `embed`），在 `inference.py` 的 `_plan()` 中登记 |
| 换向量库 | 实现 `VectorStore`（`add` / `search` / `drop` / `count`），在 `retrieval.create_vector_store()` 工厂登记 |
| 加工具 | 用 `@registry.tool(name=..., description=...)` 装饰一个返回字符串的函数，Agent 自动可见 |
| 改前端页面 | 在 `frontend/src/pages/` 新增页面并在 `App.tsx` 注册路由；状态痕迹通过 `lib/inspector.ts` 写入 Inspector |

新增功能一律先改契约（Spec / openapi），再改实现——这是本项目防范围蔓延的硬规则。

---

## 5. 持久化布局

```
backend/data/
├── memory/<session>.json     # 会话与记忆条目（原子写）
├── knowledge/<kb_id>.json    # 知识库切片与元数据
└── vector/<kb_id>.json|lance # 向量数据（Numpy 或 LanceDB 后端）
```

配置与密钥：`.env`（含 `API_KEY`）**不入库**（`.gitignore` 已排除）；`GET /api/v1/settings` 只返回 `has_api_key` 布尔值，永不回显密钥。

---

## 6. 前端架构

| 关注点 | 方案 |
|--------|------|
| 布局 | `AppShell`：左 240px 导航 / 中执行画布 / 右 320px Inspector / 底状态条 / ⌘K 命令面板 |
| 数据获取 | `lib/api.ts` 统一 REST + SSE（`postSSE` 逐帧解析 `data:` 行） |
| 执行痕迹 | `lib/inspector.ts` 轻量 store（`useSyncExternalStore`），四类：Task / Context / Action / Observation |
| 用量统计 | `lib/usage.ts` 按字符估算 token，状态条展示 |
| 样式 | `styles/tokens.css`（Tailwind v4 `@theme` + CSS 变量），组件内零硬编码颜色 |
| 图标 | 仅 `lucide-react`，16/20/24px，描边 2px，`currentColor` |

---

## 7. 测试策略

| 层次 | 覆盖 |
|------|------|
| 模块单测 | `inference` / `retrieval` / `rag` / `tools` / `agent` / `memory` 各自注入假实现，验证契约行为 |
| 端点测试 | `TestClient` 打 `/api/v1/*`，校验状态码与响应结构 |
| 前端 | `tsc --noEmit` 类型检查 + `vite build` 产物校验 |
| 门禁 | `tools/scan_emoji.py` 全仓扫描，P0 零 emoji |

测试全程离线、无需 API Key——这是"可复现"承诺的兑现方式。

---

## 8. 已知风险与未决项

详见 `docs/decisions/OPEN-DECISIONS.md`，要点：
- 桌面二进制需 Rust + 系统构建工具与分平台 sidecar 打包（ADR-001）
- LanceDB 在 Python 3.13 / win_amd64 的 wheel 可用性（ADR-003）
- Numpy 向量后端为 O(n) 全量扫描，大知识库需切 LanceDB
- 多用户 / RBAC / 云端托管不在 MVP 范围（v2.0）
