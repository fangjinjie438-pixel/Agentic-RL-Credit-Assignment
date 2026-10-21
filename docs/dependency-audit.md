# S0 候选依赖静态审计

审计日期：2026-10-22。下面只记录官方源码、发布说明、wheel 索引声明；**不代表安装解析、CPU 导入或 GPU 验证通过**。网页中展示的哈希尚未用本地下载文件复核。

| 项目 | 官方静态证据 |
| --- | --- |
| verl | v0.6.1 对应 commit `d62da4950573d7a4b7ef2362337952e7ab59e78d`，见 [commit](https://github.com/verl-project/verl/commit/d62da4950573d7a4b7ef2362337952e7ab59e78d)。[setup.py](https://github.com/verl-project/verl/blob/v0.6.1/setup.py) 的 vLLM 可选范围为 >=0.8.5,<=0.11.0；numpy<2，tensordict>=0.8.0,<=0.10.0,!=0.9.0，ray[default]>=2.41.0。PEFT 等未固定。 |
| Python | [verl](https://github.com/verl-project/verl/blob/v0.6.1/pyproject.toml) 声明 >=3.10；[vLLM](https://github.com/vllm-project/vllm/blob/v0.10.0/pyproject.toml) 声明 >=3.9,<3.13；3.11 位于声明交集。 |
| vLLM 依赖 | [cuda.txt](https://github.com/vllm-project/vllm/blob/v0.10.0/requirements/cuda.txt) 固定 torch2.7.1、torchvision0.22.1、torchaudio2.7.1，Linux x86_64 xformers0.0.31；ray[cgraph]>=2.43.0,!=2.44.*。[common.txt](https://github.com/vllm-project/vllm/blob/v0.10.0/requirements/common.txt) 要求 Transformers>=4.53.2。 |
| cu126 构建 | [v0.10.0 GPU 安装文档](https://docs.vllm.ai/en/v0.10.0/getting_started/installation/gpu.html) 的默认二进制为 cu128，需选择另发的 cu126。官方 [发布资产](https://github.com/vllm-project/vllm/releases/expanded_assets/v0.10.0) 列有 `vllm-0.10.0+cu126-cp38-abi3-manylinux1_x86_64.whl`（展示大小 344 MB）。 |
| PyTorch 构建 | 官方 cu126 索引列有相应 [torch](https://download.pytorch.org/whl/cu126/torch/)、[torchvision](https://download.pytorch.org/whl/cu126/torchvision/)、[torchaudio](https://download.pytorch.org/whl/cu126/torchaudio/) 与 [xformers0.0.31](https://download.pytorch.org/whl/cu126/xformers/) wheel；所选 manylinux_2_28 需实际 glibc>=2.28。 |
| 驱动 | [CUDA12.6 GA release notes](https://docs.nvidia.com/cuda/archive/12.6.0/cuda-toolkit-release-notes/index.html) Linux 随附驱动门槛560.28.03，CUDA12.x小版本兼容下限525.60.13；[兼容说明](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) 同时列出 PTX/JIT 和新功能边界，不能据驱动门槛直接认定训练通过。 |

vLLM cu126 的**发布页元数据** SHA256：`d3a8d58eee37f2475aedaf5b54403d9747da9ec273e802ad81b32b59ba81a87b`。候选输入文件显式指定该来源及哈希；下载失败/尚未下载时不能声称已校验 wheel。

## FSDP2、LoRA 与多轮接口

固定 v0.6.1 的 [fsdp_workers.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/workers/fsdp_workers.py) 存在 PEFT 包装、FSDP2 与 rollout_mode 参数收集分支；[fsdp_utils.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/utils/fsdp_utils.py) 提供 apply_fsdp2 和 LoRA 参数收集。`layered_summon` 路径有基础模型预载等前提，不能把接口存在当作所有配置可用。

[vllm_rollout_spmd.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/workers/rollout/vllm_rollout/vllm_rollout_spmd.py) 的 adapter 更新包含移除旧 LoRA、TensorLoRARequest 与 add_lora；[vllm_async_server.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/workers/rollout/vllm_rollout/vllm_async_server.py) 生成时检查 adapter 并传 LoRARequest。[ToolAgentLoop](https://github.com/verl-project/verl/blob/v0.6.1/verl/experimental/agent_loop/tool_agent_loop.py) 与 [AgentLoop](https://github.com/verl-project/verl/blob/v0.6.1/verl/experimental/agent_loop/agent_loop.py) 提供异步多轮及 response_mask 路径。

以上证明需要进一步验证的静态接口存在；没有证明 actor 更新的 adapter 真正在本版本组合的 rollout 使用。v0.6.1 [发布说明](https://github.com/verl-project/verl/releases/tag/v0.6.1) 还提及 CI 镜像升级到 vLLM0.11.0，不能将其视为0.10.0的背书。

## 尚需真实执行

候选解析与隔离安装、`pip check`、本地 wheel 哈希、导入、实际 Torch CUDA/NCCL、P2P 传输、vLLM 推理、FSDP2/LoRA 与多轮 adapter 同步各自单列，完整命令/日志在 PROGRESS 和 S0 文档中记录。没有通过前不生成“已验证兼容”结论，不自动升级到新矩阵。
