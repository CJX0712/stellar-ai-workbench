// Author: 晨星
// Tauri 应用装配层：挂载 shell 插件（桌面模式下用于拉起 Python 后端进程），
// 业务逻辑不在此处，全部位于 Python 后端与 TypeScript 前端。
use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                window.set_title("Stellar AI Workbench · 模块化 AI 工作台")?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("启动 Stellar AI Workbench 桌面应用失败");
}
