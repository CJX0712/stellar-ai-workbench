// Author: 晨星
// 桌面壳入口：仅做装配，业务逻辑全部在 Python 后端与 TS 前端。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    stellar_ai_workbench_lib::run()
}
