# procure_rl 包（S0–S2）

S0/S1 已验收；S2 数据代码、CPU pilot与真实教师正负轨迹过滤已执行，正式数据审核仍待验收。配置、诊断和采购环境 CPU 入口不使用 GPU；`gpu-probe` 仍默认 dry-run。S2 外部教师须显式执行参数和独立密钥，默认配置可修改。SFT 与 RL 尚未实现。

| 文件 | 用途、输入输出及调用关系 | 执行方式 |
| --- | --- | --- |
| `__init__.py` | 包版本元数据；导入不加载 GPU 库 | 由 CLI 导入，无独立运行需求 |
| `__main__.py` | argparse 入口，调用 S0 探针、S1 env.smoke 与 runtime；输入子命令、配置/新输出目录和授权，输出状态 JSON、退出码和日志 | `python -m procure_rl`，见下方完整命令 |
| `config.py` | 读取 S0 JSON，校验候选版本、模型分工、只读 GPU 边界和规划参数；输出字典或异常；不是 verl 配置验证器 | 由 `check-config` 调用 |
| `doctor.py` | 固定只读 NVIDIA/git 查询、CPU/内存/文件系统、Toolkit 路径元数据与依赖 metadata；不执行 nvcc；`collect_report` 返回字典，`write_report` 写报告，`run_doctor` 返回报告路径 | 由 `doctor` 调用 |
| `environment_probe.py` | 生成固定探针规格；在项目 `.venv-gpu` 的独立子进程检查包 metadata、verl commit、FSDP2/LoRA/AgentLoop 等入口。隐藏 GPU，禁止子进程再启动编译器/Toolkit，保留每项结构化结果与原始输出 | `check-environment` 调用；输入项目解释器/超时，输出 JSON/Markdown 报告；不是 GPU 验收 |
| `gpu_probe.py` | 按完整 UUID 隔离并二次检查授权，在有界子进程运行 BF16 前反向、双卡小量拷贝/NCCL、单卡独立 FlashAttention 或本地 Qwen3-0.6B 单提示；JSON 文件传递状态，stdout/stderr仅作诊断 | `gpu-probe` 调用；输入授权/探针/本地模型与revision，输出逐探针结果；默认无 GPU 操作 |
| `runtime.py` | 记录命令、解释器、源文件/配置 SHA256、起止时间、执行种类、验证级别和产物；未知 revision、种子或 checkpoint 为 null；GPU 入口补实际授权与模型信息 | 所有 CLI 子命令调用，写 `run.json` / `run.log` |
| [env/](env/README.md) | S1 原生工具适配、split 只读 SQLite、JSON 动作协议、独立会话、快照回放、终局与过程验证器、CPU 验收；各文件用途和 API 见子目录 | `s1-smoke`；固定数据，无模型/API/GPU |
| [data/](data/README.md) | S2真实源归一化、先划分/去重/任务/反事实、受限教师客户端、真实回放、人工/语义审核门槛；逐文件见子目录 | `s2-build`、`s2-collect`、`s2-audit`；无自动正式训练放行 |

项目根目录执行（CPU 开发 / 学校 Linux 相同）：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-config --config configs/s0.json --output logs/my-config-check
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl doctor --output logs/my-doctor --timeout 10
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-environment --output logs/my-environment --python .venv-gpu/bin/python --timeout 120
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl gpu-probe --output logs/my-gpu-dry-run
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
```

doctor 输出目录内的 `report.json` 保留每条探针的命令、退出码、原始 stdout/stderr、超时和耗时；`report.md` 为人可读索引。NVIDIA 显存字段单位 MiB，内存/文件系统字段为 bytes；进程/显存随时间变化。缺失工具与失败探针记录为 unavailable/failed，CLI 完成报告并不等于每个探针通过。运行目录存在时拒绝覆盖，换新路径重跑；无 checkpoint 恢复步骤。

`check-environment --dry-run` 只写 `probe_spec.json`，不启动子进程；正常模式逐项保存 `probes/<id>.json`，最后写 `report.json`、`report.md`。所有 ML 导入都在隐藏 GPU 的独立解释器中运行；审计钩子阻止再次执行外部程序。NumPy等库可捕获可选主机探测的 `FileNotFoundError` 并使用自身回退，报告仍记录被阻止的可执行文件名。版本或 commit 匹配只证明元数据；导入通过只证明对应接口可导入。缺包、超时和意外 CUDA 初始化均保留为失败。

学校真实 GPU 命令必须使用项目 `.venv-gpu/bin/python`；以下是用户已明确可用的 GPU 5、7 双卡命令模板，每次换新输出目录并确认授权仍有效：

```bash
PYTHONPATH=src .venv-gpu/bin/python -m procure_rl gpu-probe --execute --output logs/my-gpu-pair --gpu-uuid GPU-2e81c395-ac38-bfde-adba-34f3d967f7af --gpu-uuid GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03 --allocation-source 'user confirmation: physical GPU 5,7' --probe torch --probe nccl --timeout 180
```

实际资源会包含 CUDA 上下文与通信缓冲，不能用于仅获准“零显存”操作的 GPU 4。UUID 参数顺序确定进程内逻辑编号；代码核验运行时 UUID。单卡 `attention` / `vllm` 的完整命令、本地模型路径和项目编译器前置见 [S0](../../docs/stages/S0.md)。每个探针均有超时，超时只清理本探针的进程组；重试用新输出目录，不结束他人进程。

固定vLLM0.10.0的NVML接口只接受数字索引。其探针先在UUID可见环境核验CUDA实际设备，再通过vLLM自带的 `third_party.pynvml` 只读映射，并验证NVML索引与PCI_BUS_ID顺序一致，才将该worker的可见性转换为对应数字。报告 `visibility_conversion` 保留映射；未知UUID或顺序不一致直接失败。用户输入和其他探针仍使用UUID，不依赖空余显存建立授权。

真实 GPU 子集通过不能推断多轮 LoRA、FSDP2 训练或全栈兼容。双卡拷贝/NCCL是小规模正确性检查，不能当带宽结果。实际执行结果和日志路径见 [PROGRESS](../../PROGRESS.md)。缺少 ML 包不会阻止 doctor；`ModuleNotFoundError: procure_rl` 通常是遗漏 `PYTHONPATH=src`。

