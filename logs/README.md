# 运行证据

这里保留小型 S0 运行记录，不存模型、训练数据、凭据或 checkpoint。每次运行使用新目录；命令、执行机器、结果和产物的权威索引在根目录 PROGRESS.md。

CLI 目录通常包含 `run.json`（清单）、`run.log`（事件）和任务产物：doctor 的 `report.json` / `report.md`，或配置检查的 `validated_config.json`。测试保留 unittest 原始输出和退出码。GPU 进程与显存快照会随时间变化，不能用作设备归属证明。

路径中的时间按 Asia/Shanghai 命名；doctor 内部 UTC 时间有显式时区。没有执行的检查不会生成“通过”日志。

本轮目录 `s0-20261022T0056+0800/`：最终证据为 `config-final/`、`doctor-final/`、`tests-final/`；`bootstrap/` 保存独立解释器引导摘要，`dependencies/` 保存解析尝试/中断及固定源码审阅，`handoff-audit.json` 保存交接一致性结果。其他 config/doctor/tests 目录为保留的早期证据，不能覆盖。
