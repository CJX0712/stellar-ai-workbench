# Stellar AI Workbench

<p align="center">
  <a href="https://github.com/CJX0712/stellar-ai-workbench/actions/workflows/ci.yml"><img src="https://github.com/CJX0712/stellar-ai-workbench/actions/workflows/ci.yml/badge.svg" alt="ci"></a>
  <a href="https://github.com/CJX0712/stellar-ai-workbench/releases"><img src="https://img.shields.io/github/v/release/CJX0712/stellar-ai-workbench?sort=semver" alt="release"></a>
  <a href="https://github.com/CJX0712/stellar-ai-workbench/blob/main/LICENSE"><img src="https://img.shields.io/github/license/CJX0712/stellar-ai-workbench" alt="license"></a>
  <img src="https://img.shields.io/badge/author-%E6%99%A8%E6%98%9F-1f6feb" alt="author">
</p>

> 模块化桌面 AI 工作台 · 整合开源成果 · 端到端可运行 · 干净环境一键复现
> 作者：**晨星** · 许可：MIT

一套以**单一职责模块**拼装的桌面 AI 工作台：统一模型网关（OpenAI 兼容 + 故障转移 + 内置 Mock）、
可插拔 RAG（向量检索增强）、原生智能体编排、工具注册、记忆与知识库，前端为 React 深色工作台。

- 后端：FastAPI + 9 个可独立单测的模块（依赖倒置，运行时注入）
- 前端：React 19 + Vite 7 + Tailwind v4 + Lucide（布局：三栏工作台 + ⌘K 命令面板 + Inspector 执行痕迹）
- 桌面壳：Tauri v2 + Python sidecar
- 验证状态：**pytest 78 项全绿** · 前端 `tsc + vite build` 通过 · 端到端接口实测通过（Mock 模式，无需 API Key）

---

## 1. 特性

| 能力 | 说明 |
|------|------|
| 统一模型网关 | 一个 OpenAI 兼容端点接入任意厂商；主模型失败自动降级到 fallback，再降级到内置 Mock |
| 离线可验证 | 未配置 `API_KEY` 时全链路走 Mock Provider，**无网络也能端到端跑通**，用于 CI 与干净环境验证 |
| 可插拔 RAG | 文档切片 → 向量化 → 相似度检索 → 增强回答，返回答案与来源片段 |
| 原生智能体 | 自研 ReAct 循环（不引第三方框架），逐步产出 Thought / Action / Observation，可审计 |
| 依赖倒置的向量层 | `VectorStore` 协议 + 工厂：优先 LanceDB，缺 wheel 时**静默降级**为 Numpy 进程内实现 |
| 模块可独立验证 | 每个模块注入抽象依赖，用 Mock/fake 单测，不依赖外网与真实向量库 |
| 设计 Token 驱动 | 全部颜色走 Token，无硬编码；零 emoji 图标（统一 Lucide）；无紫粉渐变 |

---

## 2. 架构总览

```
                    ┌──────────────────────────────────────────┐
   React 19 UI  ──▶ │  API 网关 FastAPI  /api/v1/*  (routes)   │
   (三栏工作台)      └───────────────┬──────────────────────────┘
                                     │ 只做校验 + 委派，无业务逻辑
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
  InferenceProxy               RAGPipeline                    Agent
  (统一网关/降级链)         (检索 + 提示组装)          (ReAct 循环 + 工具 + 记忆)
        │                            │                            │
        ▼                            ▼                            ▼
  Provider 协议              Retrieval 抽象            ToolRegistry / MemoryStore
  ├─ OpenAICompatible        └─ VectorStore 协议        ├─ calculator（安全求值）
  └─ MockProvider               ├─ LanceVectorStore      └─ knowledge_search
                                └─ NumpyVectorStore
                                     │
                                KnowledgeStore（切片与元数据）
```

### 模块与接口契约（依赖倒置：模块只依赖抽象，运行时注入实现）

| # | 模块 | 核心接口 | 独立验证方式 |
|---|------|----------|--------------|
| 1 | `InferenceProxy` | `chat()` / `astream()` / `embed()` / `list_models()` / `rebuild()` | MockProvider + 假 Provider |
| 2 | `Retrieval` | `add()` / `query()` / `search_text()` / `backend` | `NumpyVectorStore` 临时目录 |
| 3 | `RAGPipeline` | `answer(query, kb_id, top_k)` → `{answer, sources}` | 注入 fake 检索与推理 |
| 4 | `ToolRegistry` | `register()` / `execute(name, args)` / `describe()` | 纯函数，安全求值单测 |
| 5 | `Agent` | `run(task, session, max_steps)` → 逐步 step | 注入 fake 工具与记忆 |
| 6 | `MemoryStore` | `store()` / `recall()` / `messages()` | 临时目录 JSON 落盘 |
| 7 | `KnowledgeStore` | `upsert()` / `get()` / `chunk_text()` | 切片边界单测 |
| 8 | `Settings` | pydantic-settings 加载 + `.env` 持久化 | 环境变量单测 |
| 9 | API 网关 | `/api/v1/*`（见下） | `TestClient` 端点测试 |

---

## 3. 目录结构

```
stellar-ai-workbench/
├── backend/                     # Python AI 引擎（FastAPI）
│   ├── app/
│   │   ├── main.py              # 只装配：建应用、挂路由（零业务）
│   │   ├── container.py         # 容器接线：拼装模块对象图
│   │   ├── schemas.py           # 请求/响应模型
│   │   ├── core/                # config（pydantic-settings）/ logging / settings_store
│   │   ├── api/                 # routes_{system,chat,knowledge,agents} + sse + deps
│   │   └── modules/             # inference / providers / retrieval / lancedb_store
│   │                            # rag / tools / agent / memory
│   ├── tests/                   # 78 项单测（含端点测试）
│   ├── requirements.txt         # 版本锁定（运行时）
│   ├── requirements-dev.txt     # 版本锁定（测试）
│   └── pyproject.toml           # 依赖与 pytest 配置（含 lancedb 可选 extra）
├── frontend/                    # TypeScript UI（React 19 + Vite 7）
│   └── src/
│       ├── App.tsx              # 路由装配
│       ├── components/          # AppShell / Inspector / CommandBar / StatusBar / ui
│       ├── pages/               # Chat / Knowledge / Agents / Settings
│       ├── lib/                 # api（REST+SSE）/ inspector / usage
│       └── styles/tokens.css    # Design Token（Tailwind v4 @theme）
├── src-tauri/                   # 桌面壳（Tauri v2）
│   ├── Cargo.toml / tauri.conf.json / capabilities/
│   └── src/main.rs + lib.rs
├── docs/
│   ├── SPEC.md                  # 规格契约（范围/API/页面/验收/E2E）
│   ├── openapi.yaml             # OpenAPI 3.0 契约
│   ├── design/design-tokens.json
│   └── decisions/               # ADR-001~004 + OPEN-DECISIONS
├── tools/                       # scan_emoji.py（P0 门禁）/ gen_icons.py
├── README.md · ARCHITECTURE.md · LICENSE · .gitignore
```

---

## 4. 快速开始

### 前置
- Python ≥ 3.11（已验证 3.13）
- Node ≥ 20（已验证 22）
- 桌面打包另需 Rust + 系统构建工具（见 §8）

### 4.1 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动后访问 `http://127.0.0.1:8000/docs` 查看交互式 API 文档。

> 无需 API Key：未配置时自动使用 Mock Provider，接口全部可用。

### 4.2 启动前端（开发态）

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173（已配置 /api 代理到后端）
```

### 4.3 桌面应用

```powershell
cd src-tauri
cargo tauri dev    # 开发态（自动拉起前端与窗口）
cargo tauri build  # 产出安装包（需 Rust + 系统构建工具）
```

### 4.4 想接入真实模型
在「设置」页填写 Base URL / API Key / 模型名，或在 `backend/.env` 中配置（见 §5）。

---

## 5. 配置

`backend/.env`（由「设置」页写入，或手工创建，参考 `backend/.env.example`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容端点 |
| `API_KEY` | 空 | 留空则走 Mock Provider |
| `MODEL` | `gpt-4o-mini` | 主模型 |
| `FALLBACK_MODEL` | 空 | 主模型失败后的降级目标 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 向量化模型 |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | 服务监听 |
| `VECTOR_BACKEND` | `auto` | `auto` / `lancedb` / `numpy`；auto 在 LanceDB 不可用时静默降级 |

---

## 6. API 一览（完整契约见 `docs/openapi.yaml`）

| Method | Path | 功能 |
|--------|------|------|
| GET | `/api/v1/health` | 健康检查 + 模块清单 + 当前 provider |
| GET | `/api/v1/models` | 可用模型与激活模型 |
| POST | `/api/v1/chat` | 对话（SSE 流式分片） |
| POST | `/api/v1/knowledge/add` | 文档导入知识库（切片 + 向量落盘） |
| POST | `/api/v1/rag/query` | 检索增强问答（答案 + 来源） |
| POST | `/api/v1/agents/run` | 智能体任务（SSE 逐步 Observation） |
| GET/POST | `/api/v1/settings` | 读取/更新模型配置（GET 时 key 脱敏） |

---

## 7. 测试与验证

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q        # 78 项全绿
cd ..\frontend
npm run build                              # tsc --noEmit && vite build
cd ..
python tools\scan_emoji.py                 # P0 门禁：NO_EMOJI_HITS
```

本次交付的实测证据（Mock 模式，无 API Key）：

| 检查项 | 结果 |
|--------|------|
| `pytest -q` | **78 passed**（exit 0） |
| 前端 `tsc` + `vite build` | 成功（1616 modules，dist 产出） |
| `GET /api/v1/health` | `{"status":"ok","provider":"mock","modules":[...6]}` |
| `POST /api/v1/chat` | 200，SSE 分片流式 + `done` |
| `POST /api/v1/knowledge/add` | `{"kb_id":"demo","chunk_count":2}` |
| `POST /api/v1/rag/query` | 返回 answer + 3 条来源（含相似度分数） |
| `POST /api/v1/agents/run` | 200，逐步返回 thought/action/observation |
| emoji 扫描 | 0 命中（前端/后端/文档全量） |

---

## 8. 干净环境一键复现

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q

# 前端
cd ..\frontend
npm ci          # 严格按 package-lock.json 复现
npm run build
```

依赖版本全部锁定：`backend/requirements*.txt`、`frontend/package-lock.json`、`src-tauri/Cargo.lock`（Cargo.lock 由首次 `cargo build` / `cargo tauri dev` 自动生成）。

---

## 9. 已知限制与降级设计

| 项 | 现状 | 处理 |
|----|------|------|
| 桌面二进制 | 本机无需 Rust：CI 矩阵（win/mac/linux）用 PyInstaller 打 sidecar + Tauri 出安装包 | Actions → Desktop Release 手动触发，或推 `v*` tag 自动发 Release（见 `.github/workflows/release.yml`） |
| LanceDB wheel | Python 3.13 / win_amd64 可能无可用 wheel | 自动降级为 `NumpyVectorStore`（进程内、零依赖），抽象层不变（见 ADR-003） |
| 沙箱 pip | 某些受限环境禁止写 site-packages | 可用 `pip install --target .pylibs ...` + `PYTHONPATH` 规避；干净环境无需此步 |
| Numpy 向量检索 | 全量扫描 O(n)，适合中小知识库 | 大规模场景切换 LanceDB 后端（同一 `VectorStore` 协议） |
| 多用户 / RBAC | MVP 为单机单用户（BYOK） | 规划在 v2.0（见 `docs/decisions/OPEN-DECISIONS.md`） |

---

## 10. 设计系统

深色「精密仪器」语言：画布 `#0B0C0E`、唯一强调色信号青 `#22D3C5`、发丝边框、Geist + JetBrains Mono；
布局为 左栏模块导航（240px）/ 中栏执行画布 / 右栏 Inspector（Task·Context·Action·Observation）/ ⌘K 命令面板 / 底部状态条。
图标统一 **Lucide**（16/20/24px，描边 2px）。Token 定义见 `docs/design/design-tokens.json` 与 `frontend/src/styles/tokens.css`。

---

## 11. 文档索引

| 文档 | 内容 |
|------|------|
| `docs/SPEC.md` | 规格契约：范围、API、页面、验收标准、端到端验证步骤 |
| `docs/openapi.yaml` | OpenAPI 3.0 接口契约 |
| `docs/decisions/ADR-001~004` | 桌面壳 / 推理网关 / 向量库 / 依赖锁定 四条架构决策 |
| `docs/decisions/OPEN-DECISIONS.md` | 未决事项登记册 |
| `ARCHITECTURE.md` | 深入架构说明：数据流、降级链、扩展点 |

---

## 作者

**晨星** · MIT License · 2026

本项目优先整合复用业界领先的开源成果（FastAPI / React / Vite / Tailwind / Tauri / Lucide 等），
仅在必要的编排与契约层自研，全部模块按单一职责拆分、可独立验证、可协同组成完整可运行链路。
