# 运行证据

这里保留 S0–S2 运行记录，不存模型、已发布正式训练数据、凭据或 checkpoint。S1/S2保留少量工程与真实来源pilot SQLite/轨迹，正式发布受gate限制。每次运行使用新目录；命令、执行机器、结果和产物的权威索引在根目录 PROGRESS.md。

CLI 目录通常包含 `run.json`（清单）、`run.log`（事件）和任务产物：doctor 的 `report.json` / `report.md`，或配置检查的 `validated_config.json`。测试保留 unittest 原始输出和退出码。GPU 进程与显存快照会随时间变化，不能用作设备归属证明。

路径中的时间按 Asia/Shanghai 命名；doctor 内部 UTC 时间有显式时区。没有执行的检查不会生成“通过”日志。

本轮目录 `s0-20261022T0056+0800/`：最终证据为 `config-final/`、`doctor-final/`、`tests-final/`；`bootstrap/` 保存独立解释器引导摘要，`dependencies/` 保存解析尝试/中断及固定源码审阅，`handoff-audit.json` 保存交接一致性结果。其他 config/doctor/tests 目录为保留的早期证据，不能覆盖。

S1 目录 `s1-20261022/`：`acceptance-final/` 为最终 **27/27** 真实 CPU 环境验收，含 `run.json/run.log`、报告、四个 split SQLite 与哈希清单、七条脚本轨迹/终局前快照、并发与预算/非法调用轨迹。`tests-final/` 保存 **82 项全过** 的原始 unittest 日志、结构化结果、机器/源码/测试哈希和精确包装脚本。`acceptance-v1/` 为修正整数范围前的首轮27项验收，不覆盖最终状态；`development-notes.json` 记录开发期问题、修复与证据缺失边界；`handoff-audit.json` 记录最终源码/配置/数据/产物一致性。没有GPU、教师调用或官方评分结果。

S2 `s2-20261022/`：`tests-v1/` 是最终 **136项全部通过** 的源/测试/fixture/runner哈希及原始日志；`build-real-final/` 是官方可用品牌/型号/标题隔离后的8商品7任务2对反事实，`build-engineering-final/` 是虚构工程包；`collect-{real,fixture}-engineering-final/` 各2/2回放接收，专家候选均0；`teacher-credentials-final/` 在网络前缺key而blocked；`release-audit-final/` 重放完成但正式数据withheld。`teacher-development/` 保存本地HTTP早期socket/代理失败与复验，均无外部教师调用。旧`*-v1`数据包使用ID-only索引，作为未放行历史保留，不复用为当前数据。`development-notes.json/handoff-audit.json` 记录修复、限制与一致性。

S2来源证据另存 `s2-source-parquet-v1/`：实际Range字节/哈希、首1000条选定列rows.json、实际执行脚本副本和机器/命令摘要；完整上游Parquet LFS SHA未本地验证。`s2-source-audit/` 保存HF/DeepSeek原始文档及官方隔离metadata抽取证据，官方query/persona/rubric未作为训练输入。源/数据条款见docs/s2-source-audit.md；该来源获取阶段当时没有GPU上下文、真实教师、独立8B或人工签核。

用户配置密钥后的S2接续为 `s2-20261022-api/`：`outbound-provenance-audit.json` 核验外发仅公开元数据和固定模板；`build-identity-v2/` 使用3个保守排除别名的新数据revision；`teacher-pilot-v1/` 两条拒收、`teacher-pilot-v2/` 一接收一拒收、`teacher-cache-v2/` 无新请求且完整重现。共72次新请求，估算0.0754485 USD、账单未知。`pilot-analysis/` 绑定原始报告SHA与实际格式/费用/失败统计；`review-material-v2/` 是7任务8商品私有事实审阅包和未签核表单，不是人工通过记录。`s2-official-identity-audit-20261022-v2/` 保存三个缺Brand目标的来源佐证与保守候选索引，metadata_complete仍false。独立8B执行、最终全量测试和发布决定以PROGRESS为准。

接续目录 `s0-20261022T0145+0800/`：`allocation.json`记录用户设备授权；`doctor/`记录当前硬件；`dependencies/`保留各轮解析、安装、依赖检查、FlashAttention下载校验和实装metadata；`imports-final/`保存25项隐藏GPU检查及逐项检查点；`tests-handoff/`保存当前39项CPU测试。`toolchain/`与`driver-links.json`记录独立编译器和必要驱动链接，模型下载与哈希清单在目录根。`gpu-pair/`为双卡实际通信，`gpu-final/`含新注意力内核通过及首次vLLM失败，`gpu-vllm-final/`为设备编号适配后的推理复验；最终状态逐项查报告和PROGRESS，不凭目录名推断成功。历史失败原样保留。
