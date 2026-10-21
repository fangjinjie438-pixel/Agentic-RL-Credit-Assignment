# 测试目录

本目录的测试均为 CPU 测试，只使用项目独立解释器与 `.venv-cpu`，不调用系统或共享 Python/Toolkit。
不下载模型、不访问教师 API、不创建 CUDA 上下文。doctor 的系统 Toolkit 信息仅列路径与符号链接元数据，策略为 `no_toolkit_execution`。
通过这些测试仅说明对应本地行为通过，不能证明候选依赖兼容或真实 GPU 训练通过。

| 文件 | 用途与输入输出 | 关联阶段 | 执行方式 |
| --- | --- | --- | --- |
| `test_doctor.py` | mock 只读 NVIDIA/Git 探测，检查缺失工具、失败退出码、超时、禁止运行系统 Toolkit、GPU 分配边界和 JSON/Markdown 产物；输出 unittest 结果 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_doctor.py' -v` |
| `test_config_runtime.py` | 检查候选配置、版本与设备分配边界；验证运行清单、失败日志、源码哈希和拒绝覆盖已有证据 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_config_runtime.py' -v` |

在项目根目录执行所有当前测试：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

上面的命令只使用项目独立 `.venv-cpu`；独立解释器与环境创建方式见根目录 README，禁止替换为系统 `python3`。
实际执行证据以根目录 `PROGRESS.md` 和其中的日志位置为准；新规则前的系统工具探测若被保留，只能标为历史证据。
真实 GPU 集成测试尚未实现、尚未执行；GPU 分配、P2P 实际传输、NCCL、CUDA runtime 和 LoRA 同步均待单独验收。

若出现 `ModuleNotFoundError: procure_rl`，确认从项目根目录运行并设置 `PYTHONPATH=src`。
新增测试文件时必须同步本表；不要把 mock 或本地测试写成学校 GPU 验证通过。
