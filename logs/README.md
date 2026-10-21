# 运行证据

这里保留小型 S0 运行记录，不存模型、训练数据、凭据或 checkpoint。每次运行使用新目录；命令、执行机器、结果和产物的权威索引在根目录 PROGRESS.md。

CLI 目录通常包含 `run.json`（清单）、`run.log`（事件）和任务产物：doctor 的 `report.json` / `report.md`，或配置检查的 `validated_config.json`。测试保留 unittest 原始输出和退出码。GPU 进程与显存快照会随时间变化，不能用作设备归属证明。

路径中的时间按 Asia/Shanghai 命名；doctor 内部 UTC 时间有显式时区。没有执行的检查不会生成“通过”日志。

本轮目录 `s0-20261022T0056+0800/`：最终证据为 `config-final/`、`doctor-final/`、`tests-final/`；`bootstrap/` 保存独立解释器引导摘要，`dependencies/` 保存解析尝试/中断及固定源码审阅，`handoff-audit.json` 保存交接一致性结果。其他 config/doctor/tests 目录为保留的早期证据，不能覆盖。

接续目录 `s0-20261022T0145+0800/`：`allocation.json`记录用户设备授权；`doctor/`记录当前硬件；`dependencies/`保留各轮解析、安装、依赖检查、FlashAttention下载校验和实装metadata；`imports-final/`保存25项隐藏GPU检查及逐项检查点；`tests-handoff/`保存当前39项CPU测试。`toolchain/`与`driver-links.json`记录独立编译器和必要驱动链接，模型下载与哈希清单在目录根。`gpu-pair/`为双卡实际通信，`gpu-final/`含新注意力内核通过及首次vLLM失败，`gpu-vllm-final/`为设备编号适配后的推理复验；最终状态逐项查报告和PROGRESS，不凭目录名推断成功。历史失败原样保留。
