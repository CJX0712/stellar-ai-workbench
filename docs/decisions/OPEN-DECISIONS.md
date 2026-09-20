<!-- Author: 晨星 -->

# OPEN-DECISIONS（未决项登记）

## 规范

凡「已经知道会影响架构、但当前不决断」的事项，必须登记在本文件，禁止默默跳过。每条必须包含：影响、触发条件（何时必须回头决断）、负责人、关联 ADR。

状态取值：

- `OPEN`：尚未决断，需跟踪
- `RESOLVED`：已决断，注明结论与日期
- `DROPPED`：确认不再需要

## 汇总

| ID | 标题 | 状态 | 触发条件 | 负责人 |
| --- | --- | --- | --- | --- |
| OD-001 | Tauri 桌面二进制需 Rust + MSVC 本机 / CI 构建 | RESOLVED 2026-09-21 | 已落地，无需跟进 | team-lead |
| OD-002 | lancedb / pyarrow 在 Python 3.13 + win_amd64 的 wheel 可用性 | OPEN | 知识库超约 1 万条，或启用 LanceDB 时 | backend-2 |
| OD-003 | 多用户 / RBAC 延后到 v2.0 | OPEN（已决定延后） | 出现第二个真实用户时 | team-lead / pm |
| OD-004 | Mock 静默降级的前端可见性策略 | OPEN | 前端接入 health 接口时 | frontend |

---

## OD-001: Tauri 桌面二进制需 Rust + MSVC 本机 / CI 构建

**状态**：RESOLVED（2026-09-21，选项 B）

**背景**：Tauri v2 的桌面产物需要 Rust 工具链（rustup / cargo）；Windows 上还需 MSVC 生成工具与 WebView2 运行时。同时 PyInstaller 不能跨平台编译，win / mac / linux 三套 sidecar 二进制必须在各自平台构建。

**Resolution（选项 B：CI 矩阵三平台安装包）**：

- `.github/workflows/ci.yml`：push/PR 时跑后端 pytest（ubuntu+windows 矩阵）、前端 tsc+vite build、P0 emoji 门禁。
- `.github/workflows/release.yml`：三平台矩阵（windows-latest / macos-latest / ubuntu-22.04），每台先 PyInstaller 打 Python sidecar（`backend/run_server.py` → `src-tauri/binaries/stellar-backend-<target-triple>`），再用 tauri-action 构建。
  - 推 `v*` tag → 自动创建 GitHub Release 并附三平台安装包；
  - workflow_dispatch 手动触发 → 构建产物上传为 workflow artifact。
- sidecar 的 `externalBin` 不进基础 `tauri.conf.json`（避免本地 dev 缺二进制报错），由 `src-tauri/tauri.release.conf.json` 在构建时通过 `--config` 注入。
- 图标三平台齐备：`tools/gen_icons.py` 生成 icon.ico / icon.icns / icon.png（1024）等，纯标准库实现。
- Rust 壳（`lib.rs`）负责拉起 sidecar 并在退出时回收子进程；sidecar 缺失时优雅降级（手动 uvicorn 仍可用）。
- 本机从此无需安装 Rust + MSVC；`Cargo.lock` 由 CI 首次构建生成（后续可提交回仓库以增强复现）。

**负责人**：team-lead

**关联 ADR**：ADR-001

---

## OD-002: lancedb / pyarrow 在 Python 3.13 + win_amd64 的 wheel 可用性

**状态**：OPEN

**背景**：当前 `requirements.txt` 未包含 lancedb 与 pyarrow，默认走 `NumpyVectorStore`。pyarrow 对新 CPython 版本的支持通常滞后于 CPython 发布，Python 3.13 上可能没有现成的 win_amd64 wheel，缺 wheel 时会退化为源码构建（需 MSVC）。

**影响**：

- 若 wheel 长期不可用，只能停留在 `NumpyVectorStore`，而它是 O(n) 全量扫描，知识库上万条后检索性能会成为瓶颈。
- 若强行启用，可能破坏「干净环境一键复现」。

**验证动作**：在目标平台执行 `pip download --only-binary=:all: lancedb pyarrow`，确认是否有可用 wheel；无 wheel 则维持 numpy 兜底或改用 Chroma。

**触发条件**：知识库规模超过约 1 万条，或实测检索延迟明显上升时；以及有人尝试启用 LanceDB 时。

**负责人**：backend-2

**关联 ADR**：ADR-003、ADR-004

---

## OD-003: 多用户 / RBAC 延后到 v2.0

**状态**：OPEN（已决定延后）

**背景**：MVP 是单用户本地桌面应用。配置、记忆、知识库均落在本地目录，没有用户概念，也没有鉴权。

**影响**：v2.0 若引入多用户，属于不兼容变更，需要重新设计：

- 存储分区：memory / knowledge 目录需按 `user_id` 隔离
- API 鉴权：引入 Bearer / JWT
- 配置持久化位置与作用域
- 届时需要新增 `/api/v2`，v1 保持兼容至少 6 个月

**触发条件**：出现第二个真实用户、或需要共享部署时。

**负责人**：team-lead / pm

**关联 ADR**：ADR-001（桌面形态天然倾向单用户）

---

## OD-004: Mock 静默降级的前端可见性策略

**状态**：OPEN

**背景**：ADR-002 的降级链以 Mock 收尾，因此真实 API 故障时会返回 200 与占位文本，而非报错。若前端不区分，用户会误以为得到的是真实模型回答。

**影响**：真实 API 故障被静默吞掉，用户被误导，问题难以被发现。

**待决断**：前端是否强制展示「当前为 Mock 模式」标识；以及在 health 接口降级时是否给出明确提示条。后端侧 `active_provider` 与 `last_error` 已可暴露，需确认前端消费方式。

**触发条件**：前端接入 `/api/v1/health` 或 `/api/v1/models` 时。

**负责人**：frontend

**关联 ADR**：ADR-002
