# Procure-RL

训练办公电子设备采购 Agent 发现隐藏需求、核验证据并恢复失败，研究动作级信用分配与专家纠错监督。

**唯一现行计划是 [PLAN.md](PLAN.md)**；开始工作先读 [AGENTS.md](AGENTS.md)、计划、[PROGRESS.md](PROGRESS.md) 和 [S0 操作文档](docs/stages/S0.md)。两份原稿已原样归档到 [docs/archive](docs/archive/README.md)，不再作为并行计划。

当前只实现 **S0 CPU 工程与只读诊断**，尚无环境适配、训练代码或 checkpoint。CPU 检查、服务器只读检查、GPU 集成分别记录；实时进度和日志见 PROGRESS。每阶段结束停止，不自动进入下一阶段。

## 最短运行路径

以下从项目根目录运行，适用于学校 Linux 和 CPU 开发机。标准库即可运行，无需下载模型或安装 ML 包。按用户要求，uv 将独立 Python 安装在项目内，再创建项目虚拟环境；不调用系统/共享 Python 或 Toolkit。

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv python install 3.11 --no-bin
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11 .venv-cpu
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-config --config configs/s0.json --output logs/my-config-check
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl doctor --output logs/my-doctor
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

本次实际创建环境的完整命令和每条验证结果见 [S0](docs/stages/S0.md)。项目 CPU 工具的源码支持 Python 3.10+，**本项目实际环境与 GPU 候选均使用独立 Python 3.11**。已有项目环境无需重建。输出目录必须是新的，重复执行换目录，避免覆盖证据。

`doctor` 仅读取 NVIDIA 管理信息、Toolkit 路径与包元数据，不执行系统 nvcc、不导入 torch、不创建 CUDA 上下文；输出 `report.json`、`report.md`、`run.json`、`run.log`。检查配置只证明本项目 JSON 符合计划，不能证明 verl 配置可运行。

## 依赖与 GPU 使用

待验证组合：**verl 0.6.1 + vLLM 0.10.0 官方 cu126 wheel + PyTorch 2.7.1/cu126**，Transformers 4.53.2。静态依据、候选安装与锁定流程见 [requirements](requirements/README.md)；目前没有 GPU lock，不允许把候选兼容性写成已验证。

学校按先到先得协调，通常能取得两张 A6000、偶尔三张。实际计算只用本次明确归属的 GPU；当前具体设备未确认，不凭剩余显存选卡。PIX 不等于 NVLink 或实际 P2P/NCCL 通过。不修改系统 CUDA/驱动或他人环境。

0.6B 关闭 thinking 做冒烟，4B-Instruct-2507 做主实验，8B 依开发集诊断决定。S0 不启动模型或训练；GPU 安装、CUDA/P2P/NCCL、真实多轮 LoRA 同步与训练均有独立待验收项。

## 目录导航

| 路径 | 内容 |
| --- | --- |
| `PLAN.md` / `AGENTS.md` / `PROGRESS.md` | 计划、协作约束与唯一进度 |
| [src](src/README.md) | Python 包；子目录 README 逐文件解释 |
| [tests](tests/README.md) | CPU 回归测试，GPU 集成尚未实现 |
| [configs](configs/README.md) | S0 候选规划配置，非可运行 verl 训练配置 |
| [requirements](requirements/README.md) | CPU 零依赖、GPU 候选和锁定流程 |
| [docs](docs/README.md) | 阶段操作、原稿归档和依赖来源审计 |
| [logs](logs/README.md) | 本轮执行日志、机器报告与运行清单 |
| `pyproject.toml` | 包元数据和可选 `procure-rl` 入口；直接运行无需安装构建依赖 |
| `.gitignore` | 排除环境、缓存、数据、模型、密钥和构建产物；保留小型审计日志 |

## 阶段索引

| 阶段 | 操作文档 | 当前状态 |
| --- | --- | --- |
| S0 工程与运行环境 | [S0.md](docs/stages/S0.md) | CPU 实现与只读检查；完整状态见 PROGRESS |
| S1 环境和验证器 → S7 正式评测 | 按阶段实施时创建 | 尚未实现 |
| S8 多教师 OPD | 主项目完成后独立开展 | 可选，尚未实现 |

出现 `ModuleNotFoundError` 时检查当前目录与 `PYTHONPATH=src`。输出目录已存在时使用新路径；缺少 `nvcc` 的 PATH 结果不代表系统没有其他 Toolkit。CPU 工具可重新运行无需恢复 checkpoint；真实训练与跨卡数恢复规则见 PLAN。

