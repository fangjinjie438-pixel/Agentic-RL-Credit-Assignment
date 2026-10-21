# Procure-RL 进度与交接

最近更新：2026-10-22（Asia/Shanghai；精确起止时间见各run.json）。执行机器：学校Linux `A6000`。当前阶段：**S0已完成并验收（工程、独立环境与最小GPU范围）**。下一阶段S1尚未开始；S0结束后按阶段边界停止。

## 初始基线（实施开始时的事实）

**计划已确定，代码尚未实现，服务器环境尚未验证。** 当时没有checkpoint、训练结果或已锁定GPU环境。下面记录随后实际完成的工作，不回填初始状态。

## 阶段状态

| 阶段 | 代码状态 | CPU/只读验证状态 | 学校真实GPU验证状态 |
| --- | --- | --- | --- |
| S0 工程与运行环境 | 配置、运行清单、doctor、隔离导入、授权GPU预检、代理与独立工具链完成 | 39项CPU测试、25项隐藏GPU依赖检查通过；实际硬件盘点完成 | 双卡BF16/P2P/NCCL、FlashAttention前反向、0.6B单提示推理通过；训练兼容待后续阶段 |
| S1 环境与验证器 | 未实现 | 未执行 | 未执行 |
| S2 数据流水线 | 未实现 | 未执行 | 未执行 |
| S3 SFT与真实多轮推理 | 未实现 | 未执行 | 未执行 |
| S4 终局RL baseline | 未实现 | 未执行 | 未执行 |
| S5 动作级信用分配 | 未实现 | 未执行 | 未执行 |
| S6 纠错闭环 | 未实现 | 未执行 | 未执行 |
| S7 正式评测与交付 | 未实现 | 未执行 | 未执行 |
| S8 可选OPD | 未实现，独立扩展 | 未执行 | 未执行 |

## 已完成的工程与文档

- 唯一现行[PLAN.md](PLAN.md)按修订稿（2）和用户后续指令合并，保留仍适用的论文、数据、算法公式、B0–B6与S8细节。两份原稿原样归档到[docs/archive](docs/archive/README.md)，manifest保留字节数与SHA256。
- [AGENTS.md](AGENTS.md)要求每次依次读取AGENTS、PLAN、PROGRESS和当前阶段文档；根README、[S0操作](docs/stages/S0.md)、各自主维护代码目录的逐文件README已建立。没有用空模块表示后续阶段完成。
- `src/procure_rl/`实现CLI、配置schema、运行清单/哈希、只读doctor、25项隔离检查和授权GPU探针；`tests/`覆盖配置、失败记录、进程隔离/回收、UUID与PCI映射。配置文件是项目规划schema，**不是已验证verl训练配置**。
- uv引导项目独立Python3.11.16到`.tools/python`，建立`.venv-cpu`、`.venv-gpu`与`.venv-toolchain`；所有Python执行使用项目解释器。CPU工具只用标准库，GPU包独立安装。
- `scripts/with_proxy.py`仅提取用户已授权的`proxy_on`函数为单命令启用代理，不执行整个bashrc/conda初始化，不输出代理凭据。`scripts/toolchain/cc,cxx`仅调用项目Zig，不回落系统GCC/nvcc。
- 候选解析、安装、`pip check`、隐藏GPU导入和真实GPU结果分别留证；传递依赖修复不改四个核心版本。必要验收通过后已生成S0范围的204包环境锁、独立工具链锁、实装快照与验证manifest；它们不代表全栈训练兼容。

## 实际机器、版本与授权

| 项目 | 实测事实与边界 |
| --- | --- |
| OS / CPU / 内存 | Ubuntu22.04.5、glibc2.35；2×Xeon Silver4214，48逻辑CPU；主机内存约502.6GiB |
| 磁盘 / 共享内存 | 项目卷可用约1.8TiB，`/dev/shm`约251.3GiB；观察值不代表个人配额 |
| GPU / 拓扑 | 4×A6000（49140MiB）+4×3090（24576MiB）；A6000索引1/4/5/7，4/5/7互为PIX；PIX不等于NVLink |
| 驱动 / runtime | 驱动560.35.03；nvidia-smi标签CUDA12.6；**实际Torch runtime12.6、NCCL2.26.2**，分别有GPU证据 |
| Toolkit / 编译器 | 系统CUDA10.2/11.3/11.7只列路径，未执行系统nvcc或GCC。项目没有完整Toolkit；Ziglang0.17.0独立C编译/链接/加载通过，必要系统驱动库只由项目链接使用 |
| 真实依赖 | Python3.11.16；verl0.6.1 commit `d62da4950573d7a4b7ef2362337952e7ab59e78d`；Torch2.7.1+cu126（CXX11 ABI=True）；vLLM0.10.0+cu126；Transformers4.53.2；共204包，依赖声明检查通过 |
| 补充包 | FlashAttention2.8.0.post2官方CUDA12/Torch2.7/ABITrue构建；xformers0.0.31；PEFT0.16.0、Accelerate1.8.1、TorchData0.11.0；其他实际版本见metadata与快照 |
| Git | 初始仅两份计划和隐藏只读目录；`.git`为空且非有效仓库，查询退出128；未修改只读目录，以源码SHA256追溯 |

GPU授权来自本次对话，记录于`logs/s0-20261022T0145+0800/allocation.json`：

| 物理编号 | UUID | 实际范围 |
| --- | --- | --- |
| 5 | `GPU-2e81c395-ac38-bfde-adba-34f3d967f7af` | 双卡计算；最终单卡注意力与推理选择此卡（执行前余量更多） |
| 7 | `GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03` | 双卡计算；历史FlashAttention2.8.3小内核 |
| 4 | `GPU-f772dd3f-e279-8cdc-62dd-7b39740b2063` | 只读拓扑，未计算；用户三卡附加授权以不占显存为条件，真实CUDA/P2P/NCCL会占显存 |

只在获准5/7中依据即时余量选卡，没有依据空闲显存认领其他卡，没有终止或修改他人进程。运行时先核验真实UUID；vLLM0.10.0额外需要只读NVML/PCI索引转换，授权输入仍是UUID。动态显存/进程/空间只对应采集时刻。

## 命令、结果与日志

本次接续日志根：[logs/s0-20261022T0145+0800](logs/s0-20261022T0145+0800/)。完整执行命令与缓存/代理/恢复办法见[S0](docs/stages/S0.md)，每个CLI运行保留机器、解释器、源文件哈希、实际argv和时间。

| 操作 | 实际结果 | 相对接续日志根的位置 |
| --- | --- | --- |
| `doctor --output …/doctor` | 主机只读硬件/驱动/拓扑/进程存在性检查完成；Git失败如实记录 | `doctor/report.json`、`report.md`、`run.json` |
| uv候选解析/安装 | 核心版本保持；v2→v3→v4的解析、安装与修正均保留；最终204包实装 | `dependencies/gpu-resolved-v*-candidate.txt`、`resolve*.log`、`install*.log` |
| `uv pip check --python .venv-gpu/bin/python` | 退出0，204包声明一致；此结果单独不证明运行兼容 | `dependencies/pip-check-final.log` |
| `check-environment --python .venv-gpu/bin/python --timeout 120` | **25/25通过**；GPU隐藏，禁止外部程序执行；含FSDP2/LoRA/AgentLoop实际API导入，未执行训练 | `imports-final/report.json`、`report.md`、`probes/`、`run.json` |
| `unittest discover -s tests -v` | **39项CPU测试通过，0失败/错误/跳过**；包含mock，不是GPU验收 | `tests-handoff/unittest.log`、`result.json`、`run.json` |
| 项目Zig编译、Python.h与驱动链接加载 | 退出0，C调用返回42；不调用驱动函数、不创建CUDA上下文 | `toolchain/compile.json`、`compiler-smoke.so`、`pip-check.log`；`driver-links.json` |
| GPU5/7 `--probe torch --probe nccl` | **实际通过**：两卡BF16前反向；4096bytes双向peer copy；2rank/16float NCCL all-reduce正确 | `gpu-pair/report.json`、`run.json` |
| GPU5 `--probe attention` | **实际通过**：FlashAttention2.8.0.post2，BF16小Q/K/V前反向与有限性 | `gpu-final/report.json`中的`checks.attention`；该次整体因vLLM失败而失败 |
| GPU5 `--probe vllm` | 首轮UUID解析失败；适配后的复验**通过**，生成`OK.`，3个token（含结束token），正常stop | 首轮`gpu-final/report.json`；复验`gpu-vllm-final/` |
| 模型下载/完整性 | Qwen3-0.6B固定revision八文件完成，权重1,503,300,328bytes，官方SHA256与本地一致 | `model-source*.json`、`model-download.json`、`model-verified.json` |
| NVML编号映射 | 只读确认UUID、NVML index与PCI顺序；没有创建CUDA上下文 | `nvml-pci-mapping.json` |

这些通信是正确性检查，**没有带宽、吞吐或三卡实测结论**。BF16峰值分配量不包含全部CUDA上下文开销。GPU检查只覆盖请求子集，报告明确保留`candidate_stack_compatibility=not_established`。

首次工作日志`logs/s0-20261022T0056+0800/`原样保留：唯一计划/归档、独立Python引导、配置检查、主机只读盘点、当时10项CPU测试和未完成下载。旧测试数量与未安装状态是历史事实，不能代表当前状态；旧`handoff-audit.json`仅适用当时范围。

## 失败与修复（原始证据保留）

- 网络/沙箱：早期NVML退出9、Python下载网络失败，经主机执行上下文及授权代理恢复；没有据此判断依赖冲突。前轮下载中断退出130保留。没有修改系统驱动/Toolkit。
- 来源/构建：默认vLLM wheel不是目标cu126，改用官方cu126 URL；Torch全局额外索引导致普通包候选偏移，改为四个CUDA wheel明确URL。只允许已审阅的纯Python `verl/pylatexenc/antlr4-python3-runtime`源码构建，其余二进制。
- 数据依赖：实装PyArrow26要求NumPy2，与本项目NumPy1.26冲突；修订PyArrow19.0.1、datasets3.6.0、pandas2.2.3，保存v3解析/安装。
- Hydra/构建依赖：旧Hydra/OmegaConf缺少所需API，setuptools84移除`pkg_resources`；修订Hydra1.3.2、OmegaConf2.3.0、ANTLR4.9.3与setuptools78.1.0，保存v4记录。
- 探针：初版用RuntimeError阻断NumPy可选`lscpu`探测，导致正常回退失效；改为仍禁止执行、以FileNotFoundError表达工具不可用并记录名称。异步server探针曾误要求新版类名，已按固定0.6.1改为源码实际三个接口。相关CPU测试与失败日志保留。
- FlashAttention：2.8.3虽在GPU7通过小内核，但超出xformers0.0.31前三段版本范围。改官方2.8.0.post2匹配wheel，实际SHA256为`8ed71ac092f80b079d2e6043b769135904d6e834916cb6da7d372b394581447b`；导入和GPU5小内核通过，没有忽略版本检查。旧wheel与失败记录保留。
- vLLM：0.10.0 NVML接口把可见性条目转int，首轮不能接受UUID。项目探针先核验CUDA UUID，再通过vLLM内置NVML只读核对PCI顺序并转换授权卡数字编号；不改上游、不增加顶级pynvml依赖。`communicate`异常回收缺口已修复并CPU回归通过；实际推理复验已通过，结果和原失败分开保留。

## 实际环境锁与已知限制

以下四份产物在安装、pip check、必要真实GPU检查通过后生成，版本与哈希见[validation-s0.json](requirements/validation-s0.json)：

- [linux-py311-cu126-s0.lock](requirements/linux-py311-cu126-s0.lock)：204包实际版本及明确来源，适用本机Linux x86_64/Python3.11/cu126；FA本地wheel映射回内容SHA已核对的官方URL，vLLM恢复候选URL哈希。
- [toolchain-s0.lock](requirements/toolchain-s0.lock)：独立Zig0.17.0；通过C/Python.h/驱动链接与本轮vLLM实际C launcher，未验证完整Torch Inductor C++。
- [installed-snapshot.txt](requirements/installed-snapshot.txt)：原样实装快照，含FA本地文件来源；跨机器重建使用上面的公共URL锁。
- [validation-s0.json](requirements/validation-s0.json)：机器、版本、源commit、GPU/模型、证据、产物哈希和未验证项。所有包并非均有独立下载档案SHA；installed-metadata保存的是安装RECORD摘要，不能冒充wheel档案哈希。

没有在第二个全新环境另做安装重现。vLLM运行有项目Zig的POSIX宏重定义和上游进程组析构警告，但推理、引擎退出正常，最终只读检查无本项目GPU进程遗留；原stderr保留，没有删除警告或修改上游。

## 模型、配置与验证边界

本地模型`Qwen/Qwen3-0.6B` revision **`c1899de289a04d12100db370d81485cdf75e47ca`**；权重SHA256 **`f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b`**。模型路径为`models/Qwen3-0.6B/<revision>`。GPU探针种子0，单提示关闭thinking、BF16、TP1、上下文512、并发1、最多16生成token、eager、关闭编译优化、显存比例0.2；正式2K–12K、多轮和训练配置未验证。

没有训练数据revision、策略版本、optimizer、checkpoint、训练曲线或教师API调用。4B主实验与8B诊断规则保持PLAN，尚未下载或训练。导入通过和最小推理通过均不能替代S3/S4的真实多轮、LoRA同步、FSDP2训练、连续5次更新和保存恢复验收。

## 下一步

1. 本次S0已完成，停止在阶段边界；已有独立环境保留供接续，无需重装。
2. 下一次推进S1时先读AGENTS→PLAN→PROGRESS→当前S0操作文档；进入S1再建立`docs/stages/S1.md`，核验EComAgentBench准确revision/许可证，实施固定小样本CPU环境、会话、工具、快照、终局/过程验证器。S1目前没有实施。
3. 后续GPU任务继续限定获准5/7；设备协调情况改变时更新UUID授权记录，执行前复查容量。首次在另一台机器/全新环境重建锁后重跑S0相应检查，不假定可迁移兼容。

当前没有外部信息阻塞；设备5/7和代理授权已明确。本轮全部下载、安装和GPU验收均已结束，没有本项目遗留GPU进程、训练任务或付费外部资源。清理证据`gpu-cleanup.json`；S0交接一致性结果`handoff-audit.json`。
