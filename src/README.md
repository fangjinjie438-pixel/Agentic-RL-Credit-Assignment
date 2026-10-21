# 源码目录（S0）

`procure_rl/` 是唯一自主 Python 包，逐文件说明在其 [README](procure_rl/README.md)。当前 S0 提供配置检查、运行记录、只读 doctor、隐藏 GPU 的隔离导入检查，以及显式授权后才能执行的 GPU 预检。S1 及以后模块尚未实现，没有用空模块表示完成。

本机 CPU / 学校 Linux 均从项目根目录运行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl --help
```

CPU 配置/doctor/默认 GPU dry-run 不需 ML 包；`check-environment` 子进程与真实 GPU 探针使用 `.venv-gpu` 中的候选依赖。输入输出和实际执行状态见包 README、[S0 操作](../docs/stages/S0.md) 与 [PROGRESS](../PROGRESS.md)。

