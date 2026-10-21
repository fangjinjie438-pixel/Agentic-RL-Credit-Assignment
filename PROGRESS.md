# Procure-RL 进度与交接

最近更新：2026-10-22（Asia/Shanghai；精确时间见运行清单）。执行机器：学校 Linux `A6000`。当前阶段：**S0，CPU 工程与只读预检已完成，候选 GPU 环境验收未完成**。下一阶段：S1，**本轮没有开始**。

## 初始基线（实施开始时的事实，原样保留）

**计划已确定，代码尚未实现，服务器环境尚未验证。** 当时没有 checkpoint、训练结果或已锁定 GPU 环境。下面是随后实际完成的工作，不回填初始状态。

## 阶段状态

| 阶段 | 代码状态 | CPU 验证状态 | 学校真实 GPU 验证状态 |
| --- | --- | --- | --- |
| S0 工程与运行环境 | 包结构、配置、只读 doctor、运行记录与文档已完成；GPU 环境尚未安装/锁定 | 10 项测试通过，配置实跑通过；学校主机只读报告已采集 | 未执行；S0 不标全阶段验收完成 |
| S1 环境和验证器 | 未实现 | 未执行 | 未执行 |
| S2 数据流水线 | 未实现 | 未执行 | 未执行 |
| S3 SFT 与真实多轮推理 | 未实现 | 未执行 | 未执行 |
| S4 终局 RL baseline | 未实现 | 未执行 | 未执行 |
| S5 动作级信用分配 | 未实现 | 未执行 | 未执行 |
| S6 纠错闭环 | 未实现 | 未执行 | 未执行 |
| S7 正式评测与交付 | 未实现 | 未执行 | 未执行 |
| S8 可选 OPD | 未实现，独立扩展 | 未执行 | 未执行 |

## 本轮完成与文件

- 合并唯一现行 [PLAN.md](PLAN.md)，以修订稿（2）及随后用户指令覆盖冲突，保留原稿论文、数据、公式、B0–B6、统计与 OPD 细节。两份原稿原样移动到 [docs/archive](docs/archive/README.md)，字节数与 SHA256 逐份校验，见 `manifest.json`。
- 建立根目录 [AGENTS.md](AGENTS.md)、[README.md](README.md)、本进度和 [S0 操作](docs/stages/S0.md)，要求每次先读计划、进度及当前阶段文档；所有自主代码目录都有逐文件 README。
- 新建 `pyproject.toml`、`.gitignore`、`configs/s0.json`；实现 `src/procure_rl/` 的 CLI、config、runtime、doctor，及 `tests/` 的必要 CPU 测试。代码文件用途见各目录 README。尚无采购环境、数据流水线或训练实现。
- 新建 `requirements/cpu.txt`（标准库零外部依赖）、`gpu-candidate.in` 与安装/锁定流程；[依赖静态审计](docs/dependency-audit.md) 保留官方固定来源。没有已验证兼容结论或 GPU lock。
- 用 uv 在项目 `.tools/python` 安装独立 Python3.11.16，并基于它创建 `.venv-cpu` / `.venv-gpu`。收到独立环境要求后已重建先前基于共享解释器的 CPU 环境，最终检查全部使用项目解释器，不调用系统/共享 Python 或系统 Toolkit。

## 实测环境与资源边界

| 项目 | 本轮证据 |
| --- | --- |
| OS / CPU / 内存 | Ubuntu22.04.5、glibc2.35；2×Xeon Silver4214，48逻辑CPU；物理内存约502.6GiB |
| 项目磁盘 / 共享内存 | 项目卷可用约1.8TiB，`/dev/shm` 约251.3GiB；空间为主机观察值，不代表个人配额 |
| GPU | 4×A6000（49140MiB/卡）+4×3090（24576MiB/卡）；A6000物理索引1/4/5/7，4/5/7互为PIX；UUID在报告中 |
| 驱动 / CUDA标签 | NVIDIA560.35.03；nvidia-smi显示CUDA12.6，仅驱动能力标签 |
| Toolkit | 只列路径：`/usr/local/cuda` 指向11.3，另可见10.2/11.3/11.7目录；**没有执行系统nvcc，版本未经工具运行验证**；项目Toolkit尚未安装 |
| P2P | NVIDIA只读能力表A6000间显示OK；**没有传输、带宽或NCCL实测** |
| 现存GPU任务 | 已观察其他进程，不终止/修改；不按剩余显存推断设备归属 |
| 使用规则 | 用户澄清先到先得，通常容易取得2张A6000、偶尔3张；不需要等待调度器。本次具体归属设备尚未确认，没有GPU计算 |
| 项目解释器 | `.venv-cpu/bin/python` 和 `.venv-gpu/bin/python`；base为项目 `.tools/python/cpython-3.11.16-linux-x86_64-gnu`，不是系统或共享解释器 |
| Python依赖 | CPU仅标准库；GPU候选环境尚未安装torch/verl/vLLM等。TorchCUDA/NCCL runtime未验证 |
| Git / 初始项目 | 初始仅两份计划与隐藏只读目录；`.git`为空且非有效仓库，rev-parse/status退出128；未初始化或修改该只读目录，源码通过SHA256留痕 |

动态显存、进程与磁盘以采集时刻为准，不作授权或长期容量承诺。CPU检查实际在学校服务器进行，没有声称另一台本机也通过。

## 命令、结果与日志

本轮日志根：[logs/s0-20261022T0056+0800](logs/s0-20261022T0056+0800/)。所有 Python 执行均按该目录清单核对解释器；早期系统默认环境检查只作历史探测，不作为最终独立环境验收。

| 实际操作 | 结果 | 证据位置（相对本轮日志根） |
| --- | --- | --- |
| uv Python安装、重建CPU环境、创建GPU环境 | 项目独立3.11.16建立；未安装GPU包 | `bootstrap/summary.json`（工具结果摘要，非原始终端转录） |
| `PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-config --config configs/s0.json --output …/config-final` | 退出0，仅CPU schema通过 | `config-final/run.json`、`run.log`、`validated_config.json` |
| `PYTHONPATH=src .venv-cpu/bin/python -m procure_rl doctor --output …/doctor-final --timeout 10` | 报告生成；NVIDIA六项查询成功，Git两项失败如实保留 | `doctor-final/report.json`、`report.md`、`run.json`、`run.log` |
| `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v` | **10项CPU测试通过，退出0**；含mock探针，不是GPU集成 | `tests-final/unittest.log`、`result.json`、`run.json`、`run.log` |
| 候选 `uv pip compile … --no-build` | 退出1，固定verl的动态元数据构建被策略阻止 | `dependencies/resolve.log` |
| 审阅固定源码后 `uv pip compile … --only-binary :all: --no-binary verl --no-binary pylatexenc` | 官方cu126 wheel转完整流式获取，数分钟未产出完整解析，已中断退出130；**不能认定冲突或兼容** | `dependencies/resolve-reviewed.log`、`result.json`、`preflight-interruption.json` |
| 固定verl源码本地审阅 | 实际commit匹配候选；检查setup/pyproject，无CUDA编译 | `dependencies/source-audit.json`（文件SHA256） |

完整可复制命令在 S0 操作文档；运行清单保留实际绝对解释器、argv、机器、源文件哈希与起止时间。早期 `doctor/` 在沙箱中NVML退出9，主机只读权限下 `doctor-host/` / 最终报告成功；失败报告没有被覆盖。沙箱Python下载网络失败后经获准网络路径安装成功；不是依赖不兼容，也没有自动审批拒绝。

交接前检查已通过：原稿哈希、必需文档、7个代码文件的模块说明与目录README、项目独立解释器、无Toolkit/GPU执行、8卡只读盘点，以及最终三份运行清单的源码哈希一致。结果见本轮 `handoff-audit.json`；这是文档与证据一致性检查，不是额外GPU验收。

## 候选、版本与产物

- 待验证：Python3.11 / verl0.6.1（`d62da4950573d7a4b7ef2362337952e7ab59e78d`）/ vLLM0.10.0官方cu126 / Torch2.7.1+cu126 / Transformers4.53.2。直接输入 `requirements/gpu-candidate.in`，规划配置 `configs/s0.json`；两者均非lock或兼容性证明。
- 静态核查已完成；完整解析**未完成**；GPU包安装、`pip check`、导入、实际CUDA/BF16、P2P/NCCL、FSDP2/LoRA与多轮同步**均未执行**。没有`gpu-resolved-candidate.txt`或已验证GPU锁。
- 模型revision、数据revision、policy_version、训练种子、checkpoint：**均无，尚未下载/构建/训练**。0.6B用于冒烟，4B为主实验，8B按开发集诊断决定；规划不等于模型已可运行。

## 下一步与最少外部信息

1. **继续S0**：安排完整候选下载/解析，先核对官方cu126 wheel的本地SHA256；按S0中的受控命令重跑，保存全新日志。解析成功后在`.venv-gpu`隔离安装并执行`uv pip check --python .venv-gpu/bin/python`，记录实际传递依赖；不调用系统Toolkit，不自动换框架。
2. GPU计算前需要的最少信息是：**本次可用的具体A6000物理编号/UUID及可使用时段**。不需要Slurm作业号；目前没有选卡、占卡或GPU任务。
3. 有实际设备归属后，新增S0真实GPU预检入口与操作文档，限制到该设备集合，验证Torch CUDA/BF16、vLLM最小推理和分配卡内P2P/NCCL，单列结果。0.6B真实多轮、LoRA同步、训练更新属于后续S3/S4门槛。
4. 按修订计划阶段边界，本轮停在S0，不自动实施S1。后续进入S1时先建立`docs/stages/S1.md`，再实现CPU固定小环境、约束验证、快照和会话隔离。

当前限制：GPU环境未安装且完整解析未完成；具体使用设备未确认；版本候选不能标兼容。其余S0 CPU工作已完成，没有隐含的后台解析或训练任务。
