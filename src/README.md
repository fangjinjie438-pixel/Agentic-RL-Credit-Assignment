# 源码目录（S0–S1）

`procure_rl/` 是唯一自主 Python 包，逐文件说明在其 [README](procure_rl/README.md)。S0 提供配置检查、运行记录、只读 doctor、隔离导入检查与授权 GPU 预检；S1 的 [env](procure_rl/env/README.md) 提供原生 ECom CPU 工具、只读商品访问、任务会话与验证器。S2 及以后未实现。

本机 CPU / 学校 Linux 均从项目根目录运行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl --help
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
```

CPU 配置/doctor/默认 GPU dry-run 不需 ML 包；`check-environment` 子进程与真实 GPU 探针使用 `.venv-gpu` 中的候选依赖。输入输出和实际执行状态见包 README、[S0 操作](../docs/stages/S0.md) 与 [PROGRESS](../PROGRESS.md)。

