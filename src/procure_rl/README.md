# procure_rl 包（S0）

当前只提供 CPU 工具，不调用模型、教师 API 或 GPU 计算。

| 文件 | 用途、输入输出及调用关系 | 执行方式 |
| --- | --- | --- |
| `__init__.py` | 包版本元数据；导入不加载 GPU 库 | 由 CLI 导入，无独立运行需求 |
| `__main__.py` | argparse 入口，调用 config / doctor 与 runtime；输入子命令、配置/新输出目录，输出状态 JSON、退出码和日志 | `python -m procure_rl`，见下方完整命令 |
| `config.py` | 读取 S0 JSON，校验候选版本、模型分工、只读 GPU 边界和规划参数；输出字典或异常；不是 verl 配置验证器 | 由 `check-config` 调用 |
| `doctor.py` | 固定只读 NVIDIA/git 查询、CPU/内存/文件系统、Toolkit 路径元数据与依赖 metadata；不执行 nvcc；`collect_report` 返回字典，`write_report` 写报告，`run_doctor` 返回报告路径 | 由 `doctor` 调用 |
| `runtime.py` | 记录命令、解释器、源文件/配置 SHA256、起止时间、状态和产物；未知模型/数据 revision 与 checkpoint 为 null | 两个 CLI 子命令均调用，写 `run.json` / `run.log` |

项目根目录执行（CPU 开发 / 学校 Linux 相同）：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-config --config configs/s0.json --output logs/my-config-check
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl doctor --output logs/my-doctor --timeout 10
```

doctor 输出目录内的 `report.json` 保留每条探针的命令、退出码、原始 stdout/stderr、超时和耗时；`report.md` 为人可读索引。NVIDIA 显存字段单位 MiB，内存/文件系统字段为 bytes；进程/显存随时间变化。缺失工具与失败探针记录为 unavailable/failed，CLI 完成报告并不等于每个探针通过。运行目录存在时拒绝覆盖，换新路径重跑；无 checkpoint 恢复步骤。

候选 metadata 版本匹配只代表版本字段，不能推断 CUDA runtime、安装一致性、P2P/NCCL、多轮 LoRA 同步或 GPU 训练通过。所有 GPU 计算验证固定待执行。本次实际执行结果和日志路径见 [PROGRESS](../../PROGRESS.md)。缺少 ML 包不会阻止 doctor；`ModuleNotFoundError: procure_rl` 通常是遗漏 `PYTHONPATH=src`。

