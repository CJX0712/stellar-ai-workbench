<!-- Author: 晨星 -->

# ADR-003: LanceDB 可选 + NumpyVectorStore 兜底（依赖倒置）

## Status

Accepted (2026-09-20)

## Background

RAG 需要本地嵌入式向量库。选型对比后 LanceDB 优于 Chroma / Qdrant：进程内运行、零运维、Lance 列式格式，不需要额外服务进程。

但存在落地风险：**lancedb 与 pyarrow 的二进制 wheel 在 Python 3.13 / win_amd64 上不保证可用**。pyarrow 对新 CPython 版本的支持通常滞后于 CPython 发布；缺 wheel 时会退化为源码构建，需要 MSVC 且编译耗时长，直接破坏「干净环境一键复现」这条硬需求。

实测现状：`backend/requirements.txt` **未包含** lancedb 与 pyarrow，只锁定 `numpy==2.2.1`。

## Decision

采用**依赖倒置 + 工厂回退**，让 LanceDB 成为「可选增强」而非「必需依赖」。

1. **协议**（`backend/app/modules/retrieval.py` 的 `VectorStore`）：`add` / `search` / `drop` / `count` + `name`。`Retrieval` 门面只依赖 `Embedder` 与 `VectorStore` 两个协议，不 import 任何具体后端。
2. **默认实现** `NumpyVectorStore`（`name="numpy-json"`）：numpy 余弦相似度 + JSON 落盘。纯 Python 依赖，任何平台都能装。
3. **可选实现** `LanceVectorStore`（`name="lancedb"`，`backend/app/modules/lancedb_store.py`）：`import lancedb` 为**延迟导入**，仅在工厂选中时执行；向量列为 `pa.list_(pa.float32(), dim)`，cosine 检索；用 `_dims.json` 记录各知识库维度，维度变化（换嵌入模型）时重建表以避免 schema 冲突。
4. **工厂** `create_vector_store(root, backend)`：
   - `auto`（默认）：优先 LanceDB，任何初始化异常都捕获并记 warning 后回退 `NumpyVectorStore`。
   - `lancedb`：显式指定时异常**不吞**，直接 raise，便于定位问题。
   - `numpy`：强制走纯 Python 实现。
   - 支持环境变量 `VECTOR_BACKEND` 覆盖，便于在无 wheel 的平台强制降级。

## Consequences

正面：

- 「干净环境一键复现」不再依赖 lancedb / pyarrow 的 wheel 可用性。
- 两个实现对上层行为完全一致，切换只需改配置，不改业务代码。
- 维度变化自动重建表，避免换嵌入模型后 schema 冲突导致的难查报错。

负面 / 代价：

1. **静默回退可能掩盖配置意图。** auto 模式下 LanceDB 不可用时只记 warning。约束：`/api/v1/health` 必须暴露 `vector_store` 实际后端名（`container.py` 已通过 `retrieval.backend` 暴露到 `describe()`），避免开发者误以为在用 LanceDB。
2. **两套实现需要双份测试覆盖。** 任一侧行为漂移都会导致切换后结果不一致。
3. **`NumpyVectorStore` 是 O(n) 全量扫描。** 知识库规模上万条后检索会明显变慢。届时必须有 LanceDB 或换实现，不能长期停留在兜底实现上。
4. **pyarrow 在 `lancedb_store.py` 顶层 import**（`import pyarrow as pa`）。因此该模块的导入失败由工厂的 try/except 整体接住，这是有意为之；但副作用是 pyarrow 缺失时日志只显示「LanceDB 不可用」，排查时需留意真实原因可能是 pyarrow 而非 lancedb。

## Related ADRs

- ADR-002：Mock 嵌入向量维度 64，与 `_dims.json` 的维度记录联动。
- ADR-004：lancedb / pyarrow 若后续启用，必须先进锁定流程，不得裸装。
