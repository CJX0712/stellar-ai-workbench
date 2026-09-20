<!-- Author: 晨星 -->

# ADR-004: 单一安装入口 + 锁定依赖（禁止并发 pip install）

## Status

Accepted (2026-09-20)

## Background

**事故复盘**：2026-09-20，两位工程师在 `backend/` 下用两条独立的 pip 安装线并发执行安装，导致 `.venv` 被装坏（包元数据不一致、部分包处于半装状态）。损坏的 venv 已移出仓库至 `2026-09-20-23-20-34/.venv-broken-*`，并以全新 venv 重建。

根因不在 pip 本身，而在**并发 + 无锁定 + 多入口**：同一 venv 被两个进程同时写入安装目录与 site-packages，元数据竞争导致损坏。

后续收敛动作已执行：杀掉安装进程、确认删除旧 venv、新建干净 venv、用单一 pip 入口一次性装全（`requirements.txt` + dev 三件套）。

## Decision

1. **单一入口**：`backend/requirements.txt` 是唯一安装源，命令固定为：

   ```
   python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt
   ```

   dev 三件套在同一条命令里一次装全，不得分多次执行，不得并行执行。

2. **严格锁定**：所有运行时依赖写死版本号（`==`）。当前锁定：

   | 依赖 | 版本 | 用途 |
   | --- | --- | --- |
   | fastapi | 0.115.6 | API 网关 |
   | uvicorn[standard] | 0.34.0 | ASGI 服务器 |
   | pydantic-settings | 2.7.0 | 类型化配置 |
   | openai | 1.59.6 | OpenAI 兼容接入 |
   | numpy | 2.2.1 | 兜底向量检索 |
   | python-dotenv | 1.0.1 | 本地环境变量 |

3. **uv.lock 方案写入文档**：向 uv 迁移时以 `uv.lock` 为权威锁（`uv sync` 一次装全），`requirements.txt` 作为 uv 不可用时的降级路径。二者**不得同时作为安装源**。

4. **禁止并发**：同一 venv 同一时刻只允许一个安装进程。多人协作时先确认无人安装，或各自使用独立 venv。

5. **禁止裸装**：任何依赖先落到 `requirements.txt`（或 `uv.lock`）再统一安装；禁止直接 `pip install xxx` 往共享 venv 里塞包。

## Consequences

正面：

- 干净环境可用单一命令确定性复现。
- 版本漂移被锁死，消除「我这儿能跑、你那儿不能」这类问题。

负面 / 代价：

1. **升级需显式动作**：安全补丁与新版需人工改锁文件，不会自动跟随。
2. **uv 与 requirements.txt 双轨存在漂移风险**：在完全迁移到 uv 之前，两处需同步维护，否则会出现「uv 装的」与「pip 装的」不一致。建议尽快完成迁移，只保留一个权威源。
3. **dev 依赖与运行时依赖未分离**：当前 `requirements.txt` 只锁运行时，dev 三件套另装。若 dev 依赖增多，应拆出 `requirements-dev.txt` 并在锁文件中区分。

## Related ADRs

- ADR-001：PyInstaller 的打包源必须是这个锁定的干净 venv，否则打出的二进制不可复现。
- ADR-003：lancedb / pyarrow 若启用，必须先过锁定流程。
