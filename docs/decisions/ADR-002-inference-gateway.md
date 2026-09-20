<!-- Author: 晨星 -->

# ADR-002: OpenAI 兼容统一接入 + Mock Provider + 主备降级链

## Status

Accepted (2026-09-20)

## Background

推理能力锁定为「OpenAI 兼容云端 API」。但本项目有一条更强的约束：**干净环境一键复现 + 可独立验证**。两者存在直接冲突：

- 若推理强依赖真实 API 密钥与外网，克隆仓库的新人（无密钥、离线）跑不起全链路。
- CI 无法在无密钥环境跑集成测试。
- 单测被迫打真实网络，不稳定且有成本。

因此需要一个既能接真实 OpenAI 兼容端点、又能在零配置下跑通全链路的设计。

## Decision

采用「**单 Provider 协议 + 两个实现 + 一条降级链**」。

1. **统一协议**（`backend/app/modules/providers.py` 的 `Provider`）：`chat` / `astream` / `embed`。上层只依赖协议，不依赖任何具体 SDK。
2. **两个实现**：
   - `OpenAICompatibleProvider`：官方 openai SDK（锁定 1.59.6），`base_url` 可指向任意 OpenAI 兼容端点；`client` / `async_client` 可注入以便离线单测；`max_retries=0`，重试交给上层降级链统一处理，避免双层重试放大延迟。
   - `MockProvider`：零依赖、无网络、无密钥。回复为确定性文本；向量用 `hash_embedding`（词 + 汉字 uni/bi-gram 投影到 64 维后 L2 归一化）。
3. **降级链**（`InferenceProxy._plan`）：主模型 → `fallback_model` → Mock。链尾恒为 Mock，因此正常路径不抛错。**空响应同样判定为失败**并继续降级。
4. **流式特殊处理**（`astream`）：仅在**首个分片产出之前**的失败才降级；一旦已开始输出内容则终止降级，避免内容重复。
5. **无密钥即 Mock**：`_build_remote()` 仅在 `has_api_key` 为真时构造远程 Provider；构造失败视为不可用并记 warning。

**为何 Mock 是硬要求而非可选项：**

- 它是「干净环境可验证」的唯一兜底。无密钥、无网络时，chat / RAG / Agent / 检索全链路仍可端到端跑通并断言。
- 它的向量是确定性的（无随机数），Mock 模式下检索结果稳定可断言，测试不会 flaky。
- 它让「主模型 / 备模型」降级链有终点，链尾不会悬空。

## Consequences

正面：

- 干净克隆即可 `uvicorn` 起服务并跑通全部路由，无需任何密钥。
- 单测全部离线、确定性、秒级完成。
- 换供应商只改 `base_url`，不动业务代码。

负面 / 代价：

1. **Mock 可能掩盖真实故障。** 降级到 Mock 后返回的是可读占位文本，若监控只看 HTTP 200，真实 API 故障会被静默吞掉。约束：`last_error` 与 `active_provider` 必须暴露到 `/api/v1/health` 与 `/api/v1/models`，前端须显式标注当前处于 Mock 模式。这条不做等于埋雷，登记为 OPEN-DECISIONS OD-004。
2. **语义差异。** Mock 的哈希向量无语义，相似度不等于真实嵌入相似度。Mock 只保证「链路通」，不保证「效果对」；效果验证必须配真实密钥另跑一轮。
3. **降级粒度较粗。** 当前以「整次调用」为单位降级，未做分片级续传。

## Related ADRs

- ADR-003：embed 降级到 Mock 时向量维度固定 64，与向量库的维度记录联动。
- ADR-004：openai SDK 版本锁定 1.59.6。
