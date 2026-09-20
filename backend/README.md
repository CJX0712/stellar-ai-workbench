# Stellar AI Workbench — Backend

> Author: 晨星
> FastAPI 后端：统一模型网关 + 可插拔 RAG + 原生智能体内核。
> 契约来源：`docs/SPEC.md` 第 5 节与 `docs/openapi.yaml`，本目录不新增契约外功能。

## 1. 本地启动

```powershell
# 1) 建虚拟环境并安装锁定依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2) 无密钥也能起（走 Mock Provider）
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) 冒烟
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
```

配置从环境变量或 `backend/.env` 读取，模板见 `.env.example`。
**未配置 `API_KEY` 时，全部推理链路自动降级到 `MockProvider`，端到端可离线跑通。**

## 2. 目录与分层（依赖只能向下）

```
app/
  main.py             # 只装配：创建 FastAPI、挂 CORS、注册路由，零业务逻辑
  core/config.py      # Settings（pydantic-settings）+ .env 持久化
  core/logging.py     # 日志初始化
  core/settings_store.py  # 运行期设置读写（api_key 只对外暴露 has_api_key）
  schemas.py          # Pydantic 请求/响应模型
  api/                # 路由层：参数校验 -> 调 service/module，不含业务
  modules/
    providers.py      # Provider 协议 + MockProvider + OpenAICompatibleProvider
    inference.py      # InferenceProxy：主模型 -> fallback -> Mock 故障转移
    retrieval.py      # Retrieval + VectorStore 抽象 + NumpyVectorStore
    lancedb_store.py  # LanceVectorStore（可替换实现）
    rag.py            # RAGPipeline：检索 -> 组装提示 -> 推理
    tools.py          # ToolRegistry：calculator / knowledge_search
    agent.py          # Agent：原生 ReAct 循环，产出 {type,index,thought,action,observation}
    memory.py         # MemoryStore（会话记忆落盘）+ KnowledgeStore（切片/元数据）
```

铁律：Controller 不直连存储，业务逻辑在 modules，路由只做校验与编排。

## 3. 模块契约（可独立注入 mock 单测）

| 模块 | 关键接口 |
|------|----------|
| `InferenceProxy` | `chat(messages, model=None, **opts) -> str`、`astream(messages, model=None)`、`embed(texts, model=None) -> list[list[float]]` |
| `Retrieval` | `add(kb_id, texts, metas=None) -> int`、`query(kb_id, vec, top_k=4) -> list[Hit]`（另有 `search_text`） |
| `RAGPipeline` | `answer(query, kb_id, top_k=4, model=None) -> {answer, sources}` |
| `ToolRegistry` | `@registry.tool(name=...)`、`execute(name, args) -> str` |
| `Agent` | `run(task, session=None, max_steps=6)` 异步产出步骤字典 |
| `MemoryStore` | `store(session, turn)`、`recall(session, k)`；落盘 `data/memory/<session>.json` |

## 4. API 端点（对齐 openapi.yaml）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/health` | `{status, provider, modules}` |
| GET | `/api/v1/models` | `{active, models[]}` |
| POST | `/api/v1/chat` | SSE `text/event-stream` |
| POST | `/api/v1/knowledge/add` | `{kb_id, chunk_count}` |
| POST | `/api/v1/rag/query` | `{answer, sources[]}` |
| POST | `/api/v1/agents/run` | SSE 逐步返回 |
| GET/POST | `/api/v1/settings` | GET 时 `api_key` 脱敏为 `has_api_key` |

CORS 放行 `http://localhost:5173`、Vite preview 端口与 Tauri 源（`tauri://localhost`、`http://tauri.localhost`）。

## 5. 依赖替换说明

### 5.1 向量库：LanceDB -> 进程内 numpy（可回退）

- **Spec 首选**：LanceDB `0.24.x`（进程内、零运维），实现在 `app/modules/lancedb_store.py`。
- **替换原因**：LanceDB 依赖 `pyarrow` 原生扩展，在部分平台（含无预编译 wheel 的 Python 次版本）不可用。
  为保证「干净环境一键复现」这条 P0 验收不被单一原生依赖卡死，`retrieval.py` 保留了纯 Python 的
  `NumpyVectorStore`（numpy 余弦相似度 + JSON 落盘 `data/vector/<kb>.json`）作为对等实现。
- **抽象未变**：两者都实现同一个 `VectorStore` 协议（`add` / `search` / `drop` / `count`），
  `Retrieval` 只依赖协议，替换不波及上层。
- **如何选择**：`create_vector_store(root, backend)` 默认 `auto` —— 先试 LanceDB，初始化失败自动回退 numpy；
  也可用环境变量 `VECTOR_BACKEND=lancedb|numpy` 强制指定。运行 `GET /api/v1/health` 可看到实际生效的后端。

### 5.2 推理：OpenAI 兼容端点 -> MockProvider

- 未配置 `API_KEY` 或上游 4xx/5xx 时，按 `主模型 -> fallback_model -> mock` 逐级降级（AC-03 / AC-04）。
- `MockProvider` 的向量化是确定性哈希嵌入（词 + 汉字 uni/bi-gram，L2 归一化），
  无随机数、无网络，保证离线检索结果可复现。

### 5.3 安装方式说明

本环境的 pip 安装受沙箱批量删除保护限制，`backend/.venv` 采用「`pip download` 取 wheel + 解压到
site-packages」的方式落地依赖，因此 `Scripts/uvicorn.exe`、`Scripts/pytest.exe` 等控制台脚本不生成。
请统一用模块方式运行：`python -m uvicorn ...`、`python -m pytest ...`。功能与依赖版本不受影响，
`requirements.txt` 与 `requirements.lock.txt` 仍是权威版本清单。

## 6. 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

每个模块拥有独立单测（推理用 MockProvider、检索用内存向量、工具用 fake、Agent 注入 mock），
并额外用 `fastapi.testclient.TestClient` 打全部端点。**整套测试在无 API key、无网络的环境下全绿。**
