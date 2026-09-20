<!-- Author: 晨星 -->

# ADR-001: 桌面壳采用 Tauri v2 + Python sidecar

## Status

Accepted (2026-09-20)

## Background

产品形态锁定为桌面应用，AI 能力由 Python 侧提供（FastAPI 承载 RAG / Agent / Tools）。需要一个桌面壳把 Web 前端与 Python 后端打包成单一可分发应用，并满足「干净环境一键复现」。

三个候选：Tauri v2、Electron（33+）、Neutralino（5.x）。

约束条件：

- Python 后端必须作为独立进程随应用分发，不能在壳内用别的语言重写一遍。
- 分发体积与冷启动是桌面端体验的硬指标。
- 构建与复现必须可脚本化，不依赖手工配置。

## Decision

选 **Tauri v2（>= 2.11.x）+ Python sidecar**。

理由：

1. **体积与内存**：Tauri 使用系统 WebView（Windows WebView2 / macOS WebKit / Linux WebKitGTK），不内嵌 Chromium。安装包 3–12 MB、空闲内存 30–70 MB。Electron 需内嵌 Chromium 与 Node，安装包 120–220 MB、空闲内存 150–400 MB。在需要分发的桌面 MVP 上这是数量级差异。
2. **sidecar 是一等公民**：Tauri v2 正式支持 bundled sidecar（`externalBin`）。Python 侧用 PyInstaller 打成单文件可执行随包分发，由 Rust 侧 spawn 并回收，前端通过 localhost HTTP 与 FastAPI 通信。Electron 与 Neutralino 都只能自己用 `child_process` 拉起并管理生命周期，Neutralino 更弱（无原生 sidecar 声明机制）。
3. **能力式权限**：Tauri v2 默认全禁，shell / sidecar / fs / dialog 需显式授权。对处理本地数据的 AI 工具是必要的。
4. **前端栈不受限**：Tauri 只消费静态产物，React 19 + Vite 7 的 `dist` 直接可用。

**版本锚定**：Tauri 2.11.x（2.0.0 于 2024-10-02 GA，2.11.4 为 2026-06-30 安全修复版）。`Cargo.lock` 必须提交。

## Consequences

正面：

- 分发体积小、冷启动快。
- 前端产物与后端二进制解耦，可各自独立迭代与测试。
- Python 侧保持纯 Python 工程（FastAPI），不被 Node / Electron 绑定。

负面 / 必须接受的代价：

1. **sidecar 不能跨平台编译。** PyInstaller 产出的可执行文件与构建机的 OS / Arch 强绑定（win-x64、mac-arm64、linux-x64 各自产出）。因此「一键复现」在桌面分发层面不成立，必须走 CI 矩阵分平台构建：GitHub Actions 上 windows-latest / macos-latest / ubuntu-latest 各跑一次 PyInstaller + `tauri build`。
2. **构建链前置依赖变重**：需要 Rust 工具链（rustup + cargo），Windows 还需 MSVC 生成工具与 WebView2 运行时。首次构建耗时长。此项登记为 OPEN-DECISIONS OD-001。
3. **进程回收陷阱**：PyInstaller 单文件模式是 bootloader + 子进程结构，Tauri 只持有 bootloader 的 pid，直接 kill 会残留 Python 子进程，导致退出应用后端口仍被占用、下次启动失败。必须按进程名显式终止或改用目录模式并自行管理子进程树。

## Related ADRs

- ADR-002（推理网关）：sidecar 内的 FastAPI 只做编排，业务模块不直连 SDK。
- ADR-003（向量库）：lancedb / pyarrow 体积很大，直接影响 sidecar 打包后的二进制大小。
- ADR-004（依赖锁定）：PyInstaller 的打包源必须是锁定后的干净 venv。
