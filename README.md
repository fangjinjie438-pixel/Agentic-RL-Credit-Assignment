# Procure-RL

训练办公电子设备采购 Agent 发现隐藏需求、核验证据并恢复失败，研究动作级信用分配与专家纠错监督。

**唯一现行计划是 [PLAN.md](PLAN.md)**；开始工作先读 [AGENTS.md](AGENTS.md)、计划、[PROGRESS.md](PROGRESS.md) 和当前 [S2 操作文档](docs/stages/S2.md)。两份原稿已原样归档到 [docs/archive](docs/archive/README.md)，不再作为并行计划。

**S2 已执行真实教师小规模采集与离线重现，数据审核仍待完成。** 第二批2条真实轨迹中1条通过硬约束、证据与回放验收，1条拒收；固定来源、先划分、去重和反事实流水线保留。正式数据 withheld，尚未开始 S3。逐项证据及当前独立复核状态见 [PROGRESS](PROGRESS.md)。

**教师默认值由 Codex 根据用户授权暂选，可修改：[configs/s2-teacher.json](configs/s2-teacher.json)。** 当前为 `deepseek-flash`、关闭 thinking，未实测为本项目最优；密钥已就绪，单独放 `.secrets/deepseek_api_key`。两批共72次请求，按保守价格估算0.0754485 USD，实际账单未知。选择理由、别名/价格边界及操作见 [S2](docs/stages/S2.md)。

## 最短运行路径

以下从项目根目录运行，适用于学校 Linux 和 CPU 开发机。标准库即可运行，无需下载模型或安装 ML 包。按用户要求，uv 将独立 Python 安装在项目内，再创建项目虚拟环境；不调用系统/共享 Python 或 Toolkit。

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv python install 3.11 --no-bin
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11 .venv-cpu
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-config --config configs/s0.json --output logs/my-config-check
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl doctor --output logs/my-doctor
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-build --config configs/s2.json --output logs/my-s2-build
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --dataset logs/my-s2-build/dataset --output logs/my-s2-engineering --engineering --limit 2
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

本次实际创建环境的完整命令和每条验证结果见 [S0](docs/stages/S0.md)。项目 CPU 工具的源码支持 Python 3.10+，**本项目实际环境与 GPU 候选均使用独立 Python 3.11**。已有项目环境无需重建。输出目录必须是新的，重复执行换目录，避免覆盖证据。

`doctor` 仅读取 NVIDIA 管理信息、Toolkit 路径与包元数据，不执行系统 nvcc、不导入 torch、不创建 CUDA 上下文；输出 `report.json`、`report.md`、`run.json`、`run.log`。检查配置只证明本项目 JSON 符合计划，不能证明 verl 配置可运行。

S1 的 `s1-smoke` 在新运行目录构建四个物理独立的 split SQLite 文件，执行七条真实工具脚本轨迹，保存终局前快照、逐步事件、独立规格真值比较及 `report.json`。上游 commit、代码许可和评分差异见 [ECom 审计](docs/ecom-upstream-audit.md)；完整官方数据库和 LLM judge 未运行。终局奖励检查硬约束，证据是否完整交付另由 `delivery_success` 诊断。

安装候选依赖后，可用 CPU 入口分别启动隐藏 GPU 的独立导入进程；GPU 探针默认只生成配置，不启动子进程、不导入 ML 包：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-environment --output logs/my-environment-check --python .venv-gpu/bin/python --timeout 120
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl gpu-probe --output logs/my-gpu-dry-run
```

真实计算必须用 `.venv-gpu/bin/python`，加完整 UUID、分配来源及 `--execute`；双卡 BF16/P2P/NCCL、单卡 FlashAttention 和本地 0.6B vLLM 命令见 [S0](docs/stages/S0.md)。导入通过或单提示推理通过不等于训练软件栈全部兼容。

## 依赖与 GPU 使用

默认验证组合：**verl 0.6.1 + vLLM 0.10.0 官方 cu126 wheel + PyTorch 2.7.1/cu126**，Transformers 4.53.2。静态依据、候选安装与锁定流程见 [requirements](requirements/README.md)；候选、解析结果、安装快照与注明验证范围的实际环境锁分别保存，不能相互替代。

四个核心包保持不变；传递依赖与FlashAttention的实际修正见[依赖审计](docs/dependency-audit.md)。已生成GPU与工具链的S0环境锁、原始安装快照和验证范围文件；[从锁重建命令](requirements/README.md)明确使用项目解释器与受控源码白名单。锁固定版本与来源，未对每个包独立核验完整归档哈希，也尚未在第二个全新环境重装验收；真实多轮、LoRA/FSDP2训练留待后续阶段。

学校按先到先得协调，通常能取得两张A6000、偶尔三张。S0历史使用5/7，原授权记录保留；**本次S2独立审核仅使用用户直接确认的GPU5**，当前授权为 `logs/s2-20261022-api/allocation-user-confirmed.json`，范围7任务单卡推理、不训练。GPU4的历史附加条件是“不占显存”，因此仅作只读查询。后续任务须核对当次有效分配范围；空闲显存不能证明归属，PIX不能证明实际通信通过。不修改系统CUDA/驱动或他人环境。

0.6B关闭thinking做冒烟，4B-Instruct-2507做主实验，主实验是否改用8B仍依开发集诊断决定。S2使用独立8B审核数据属于PLAN预定的审核分工，不改变训练模型决策；其实际执行证据见PROGRESS。S0只验最小环境；真实多轮LoRA同步与训练属于S3/S4。项目使用独立 `.venv-cpu`、`.venv-gpu` 和按需 `.venv-toolchain`；编译器包装见 [scripts](scripts/README.md)，不回落系统GCC/Toolkit。网络问题可用用户授权的 `proxy_on`，包装命令见S0。

## 目录导航

| 路径 | 内容 |
| --- | --- |
| `PLAN.md` / `AGENTS.md` / `PROGRESS.md` | 计划、协作约束与唯一进度 |
| [src](src/README.md) | Python 包；子目录 README 逐文件解释 |
| [tests](tests/README.md) | CPU 回归与探针边界测试；mock 不替代 GPU 执行 |
| [configs](configs/README.md) | S0/S1 工程配置、S2真实/工程来源和可修改教师默认值，非 verl 训练配置 |
| [fixtures](fixtures/README.md) | S1虚构工程夹具、S2真实来源摘录与官方排除索引，非已放行训练集 |
| [third_party](third_party/README.md) | 固定 ECom 原样源码、许可和逐文件哈希 |
| [requirements](requirements/README.md) | CPU 零依赖、GPU 候选和锁定流程 |
| [scripts](scripts/README.md) | 单命令代理包装与项目独立编译器入口 |
| [docs](docs/README.md) | 阶段操作、原稿归档和依赖来源审计 |
| [logs](logs/README.md) | 本轮执行日志、机器报告与运行清单 |
| `pyproject.toml` | 包元数据和可选 `procure-rl` 入口；直接运行无需安装构建依赖 |
| `.gitignore` | 排除环境、缓存、数据、模型、密钥和构建产物；保留小型审计日志 |

## 阶段索引

| 阶段 | 操作文档 | 当前状态 |
| --- | --- | --- |
| S0 工程与运行环境 | [S0.md](docs/stages/S0.md) | 声明范围验收通过；逐项证据见PROGRESS |
| S1 环境和验证器 | [S1.md](docs/stages/S1.md) | 固定小数据 CPU 验收通过，阶段结束 |
| S2 数据流水线 | [S2.md](docs/stages/S2.md) | 真实教师采集/正负过滤/缓存重现完成；人工、独立语义及官方家族审核状态见PROGRESS |
| S3 SFT → S7 正式评测 | 按阶段实施时创建 | 尚未实现 |
| S8 多教师 OPD | 主项目完成后独立开展 | 可选，尚未实现 |

出现 `ModuleNotFoundError` 时检查当前目录与 `PYTHONPATH=src`。输出目录已存在时使用新路径；缺少 `nvcc` 的 PATH 结果不代表系统没有其他 Toolkit。CPU 工具可重新运行无需恢复 checkpoint；真实训练与跨卡数恢复规则见 PLAN。

