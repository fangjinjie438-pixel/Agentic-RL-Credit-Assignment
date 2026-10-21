# 测试目录

本目录的测试均为 CPU 测试，只使用项目独立解释器与 `.venv-cpu`，不调用系统或共享 Python/Toolkit。
不下载模型、不访问教师 API、不创建 CUDA 上下文。doctor 的系统 Toolkit 信息仅列路径与符号链接元数据，策略为 `no_toolkit_execution`。
通过这些测试仅说明对应本地行为通过，不能证明候选依赖兼容或真实 GPU 训练通过。

| 文件 | 用途与输入输出 | 关联阶段 | 执行方式 |
| --- | --- | --- | --- |
| `test_doctor.py` | mock 只读 NVIDIA/Git 探测，检查缺失工具、失败退出码、超时、禁止运行系统 Toolkit、GPU 分配边界和 JSON/Markdown 产物；输出 unittest 结果 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_doctor.py' -v` |
| `test_config_runtime.py` | 检查候选配置、版本与设备分配边界；验证运行清单、失败日志、源码哈希和拒绝覆盖已有证据 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_config_runtime.py' -v` |
| `test_environment_probe.py` | mock ML 导入与子进程，检查项目解释器限定、GPU隐藏、离线模式、metadata/commit记录、超时/失败不误报，以及禁止子进程执行编译器/Toolkit；输出 unittest 结果 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_environment_probe.py' -v` |
| `test_gpu_probe.py` | mock GPU worker 与临时JSON结果，检查默认dry-run无ML导入、完整UUID/来源门禁、单卡模型限制、环境清理/缓存隔离、超时及通信异常回收、运行时UUID核验，以及vLLM的只读UUID/PCI索引映射和失败拒绝 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_gpu_probe.py' -v` |

在项目根目录执行所有当前测试：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

上面的命令只使用项目独立 `.venv-cpu`；独立解释器与环境创建方式见根目录 README，禁止替换为系统 `python3`。
实际执行证据以根目录 `PROGRESS.md` 和其中的日志位置为准；新规则前的系统工具探测若被保留，只能标为历史证据。
真实 GPU 预检入口位于 `src/procure_rl/gpu_probe.py`，完整执行方式见 [S0](../docs/stages/S0.md)。本目录测试不执行它的计算路径；实际 CUDA、双卡 P2P/NCCL、独立 FlashAttention 与 vLLM 结果分别由运行报告证明。真实多轮 LoRA 同步与训练仍属于 S3/S4，不能由本目录测试替代。

若出现 `ModuleNotFoundError: procure_rl`，确认从项目根目录运行并设置 `PYTHONPATH=src`。
新增测试文件时必须同步本表；不要把 mock 或本地测试写成学校 GPU 验证通过。
