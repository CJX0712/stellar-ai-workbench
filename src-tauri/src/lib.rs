// Author: 晨星
// Tauri 应用装配层：挂载 shell 插件，启动时拉起 Python 后端 sidecar，
// 退出时回收子进程避免残留。业务逻辑全部位于 Python 后端与 TS 前端，此处零业务。
use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// 持有 sidecar 子进程句柄，应用退出时统一回收。
struct SidecarChild(Mutex<Option<CommandChild>>);

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                window.set_title("Stellar AI Workbench · 模块化 AI 工作台")?;
            }
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let cmd = match handle.shell().sidecar("stellar-backend") {
                    Ok(cmd) => cmd,
                    Err(e) => {
                        // 开发模式没有 sidecar 二进制：优雅降级，
                        // 用户可手动 `uvicorn app.main:app` 启动后端。
                        eprintln!("[stellar] sidecar 解析失败，可手动启动后端: {e}");
                        return;
                    }
                };
                match cmd.spawn() {
                    Ok((mut rx, child)) => {
                        handle.manage(SidecarChild(Mutex::new(Some(child))));
                        // 持续排空输出管道，防止后端日志阻塞在缓冲区
                        while let Some(_event) = rx.recv().await {
                            // 静默排空；排障时可在此打印事件内容
                        }
                    }
                    Err(e) => {
                        eprintln!("[stellar] sidecar 启动失败，前端将以未连接状态运行: {e}");
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("构建 Stellar AI Workbench 桌面应用失败")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(state) = app.try_state::<SidecarChild>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(child) = guard.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        });
}
