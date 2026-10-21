# S0 依赖来源与实际问题审计

审计日期：2026-10-22。静态来源与本轮实际错误分开记录；**静态声明不能替代安装、导入或GPU执行**。当前最终状态以PROGRESS为准，历史失败保留；网页资产哈希不能代替本地校验。

| 项目 | 官方静态证据 |
| --- | --- |
| verl | v0.6.1 对应 commit `d62da4950573d7a4b7ef2362337952e7ab59e78d`，见 [commit](https://github.com/verl-project/verl/commit/d62da4950573d7a4b7ef2362337952e7ab59e78d)。[setup.py](https://github.com/verl-project/verl/blob/v0.6.1/setup.py) 的 vLLM 可选范围为 >=0.8.5,<=0.11.0；numpy<2，tensordict>=0.8.0,<=0.10.0,!=0.9.0，ray[default]>=2.41.0。PEFT 等未固定。 |
| Python | [verl](https://github.com/verl-project/verl/blob/v0.6.1/pyproject.toml) 声明 >=3.10；[vLLM](https://github.com/vllm-project/vllm/blob/v0.10.0/pyproject.toml) 声明 >=3.9,<3.13；3.11 位于声明交集。 |
| vLLM 依赖 | [cuda.txt](https://github.com/vllm-project/vllm/blob/v0.10.0/requirements/cuda.txt) 固定 torch2.7.1、torchvision0.22.1、torchaudio2.7.1，Linux x86_64 xformers0.0.31；ray[cgraph]>=2.43.0,!=2.44.*。[common.txt](https://github.com/vllm-project/vllm/blob/v0.10.0/requirements/common.txt) 要求 Transformers>=4.53.2。 |
| cu126 构建 | [v0.10.0 GPU 安装文档](https://docs.vllm.ai/en/v0.10.0/getting_started/installation/gpu.html) 的默认二进制为 cu128，需选择另发的 cu126。官方 [发布资产](https://github.com/vllm-project/vllm/releases/expanded_assets/v0.10.0) 列有 `vllm-0.10.0+cu126-cp38-abi3-manylinux1_x86_64.whl`（展示大小 344 MB）。 |
| PyTorch 构建 | 官方 cu126 索引列有相应 [torch](https://download.pytorch.org/whl/cu126/torch/)、[torchvision](https://download.pytorch.org/whl/cu126/torchvision/)、[torchaudio](https://download.pytorch.org/whl/cu126/torchaudio/) 与 [xformers0.0.31](https://download.pytorch.org/whl/cu126/xformers/) wheel；所选 manylinux_2_28 需实际 glibc>=2.28。 |
| 驱动 | [CUDA12.6 GA release notes](https://docs.nvidia.com/cuda/archive/12.6.0/cuda-toolkit-release-notes/index.html) Linux 随附驱动门槛560.28.03，CUDA12.x小版本兼容下限525.60.13；[兼容说明](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) 同时列出 PTX/JIT 和新功能边界，不能据驱动门槛直接认定训练通过。 |

vLLM cu126的**发布页元数据**SHA256为 `d3a8d58eee37f2475aedaf5b54403d9747da9ec273e802ad81b32b59ba81a87b`，候选及实际锁URL含该哈希。安装器按此输入安装；本轮没有另存独立本地归档SHA256核对，不把它等同FlashAttention的流式下载哈希实测。

## 本轮候选来源与辅助依赖

Torch、TorchVision、TorchAudio与xformers在输入中使用明确的官方cu126 wheel URL，其他包使用PyPI。这个来源策略避免uv在全局额外索引上先找到普通包的有限版本；uv的默认索引行为见[官方兼容说明](https://docs.astral.sh/uv/pip/compatibility/#packages-that-exist-on-multiple-indexes)。来源策略调整不改变Torch2.7.1、vLLM0.10.0、verl0.6.1与Transformers4.53.2四个核心候选。

| 输入 | 静态理由与执行边界 |
| --- | --- |
| PEFT0.16.0 | 为Transformers4.53.2时代的Qwen3/LoRA接口选择显式候选，见[固定版本源码](https://github.com/huggingface/peft/tree/v0.16.0)；需要实际导入和后续LoRA训练证明，不能仅由版本时间认定兼容。 |
| Accelerate1.8.1 | 显式固定辅助候选，见[固定版本常量源码](https://github.com/huggingface/accelerate/blob/v1.8.1/src/accelerate/utils/constants.py)；不改变项目FSDP2/LoRA验收门槛。 |
| TorchData0.11.0 | 为固定verl所用StatefulDataLoader提供显式候选，见[该版本说明](https://github.com/pytorch/data/blob/v0.11.0/README.md)；安装、导入与数据位置恢复仍分别验证。 |
| FlashAttention2.8.0.post2 | 独立 `flash_attn` 来自[官方资产](https://github.com/Dao-AILab/flash-attention/releases/expanded_assets/v2.8.0.post2)，选 `cu12torch2.7cxx11abiTRUE-cp311`，匹配实际Torch ABI。2.8.3被xformers0.0.31拒绝后调整，替换后的导入与内核已重新通过；CUDA12家族不是cu126专用承诺。 |
| Ziglang0.17.0 | 项目独立C/C++编译器候选，安装在 `.venv-toolchain`，供Triton launcher使用；包装器不回落系统GCC/nvcc。版本、编译/链接与GPU JIT分别留证据，不据包装器存在认定全C++工具链兼容。 |

FlashAttention2.8.0.post2官方wheel SHA256为 `8ed71ac092f80b079d2e6043b769135904d6e834916cb6da7d372b394581447b`，本轮下载255941661 bytes且哈希相符；输入在 `requirements/attention-candidate.in`。历史2.8.3资产哈希为 `cd1a45ebfc1731a13e55ad68e0c9ad92390ddfffba306f9222be67c6d5a805af`，其内核通过不能替代修订版复验。

vLLM自带 `vllm.vllm_flash_attn` 与训练侧 `flash_attn` 不同，单提示推理不能证明独立包可训练。`.tools/cuda-driver/lib`只链接必要NVIDIA驱动库，不是Toolkit；不执行系统nvcc，CUDA源码扩展需另建项目Toolkit后验收。

## 实际错误与修正依据

日志根为 `logs/s0-20261022T0145+0800/`；四个核心版本始终未改。v2/v3/v4解析和安装逐次保留，以下修正均针对真实错误，不据resolver通过认定运行正常。

| 实际问题与证据 | 修正与边界 |
| --- | --- |
| `dependencies/datasets-initial.json`：PyArrow26实际导入要求NumPy>=2，环境为1.26.4；不是预先担心的PyExtensionType报错。 | 保留verl的NumPy<2，固定PyArrow19.0.1、Datasets3.6.0、Pandas2.2.3；[Arrow19安装说明](https://arrow.apache.org/docs/19.0/python/install.html)与[Datasets3.6.0依赖](https://github.com/huggingface/datasets/blob/3.6.0/setup.py)作为固定依据。 |
| `imports-initial/report.json`：Hydra导入缺 `pkg_resources`，verl配置导入缺OmegaConf的 `MISSING`。 | 固定Hydra1.3.2、OmegaConf2.3.0、ANTLR4.9.3、Setuptools78.1.0；[Hydra固定依赖](https://github.com/hydra-ecosystem/hydra/blob/v1.3.2/requirements/requirements.txt)、[OmegaConf导出](https://github.com/omry/omegaconf/blob/v2.3.0/omegaconf/__init__.py)、[Setuptools发布](https://pypi.org/project/setuptools/78.1.0/)供追溯；ANTLR纯Python源码加入受控白名单。 |
| 初次隐藏GPU导入被NumPy的可选主机探测（如lscpu）触发子进程门禁。 | 探针改为阻止并记录可选外部探测，维持禁止编译器/Toolkit/shell；不能把探针策略导致的失败算作GPU库不兼容。 |
| `imports-v4/probes/xformers_ops.json`：实际拒绝FlashAttention2.8.3；但 `gpu-attention/` 已证明其在GPU7上的小内核前反向。 | [xformers0.0.31源码](https://github.com/facebookresearch/xformers/blob/v0.0.31/xformers/ops/fmha/flash.py)只比较版本前三段，接受2.7.1至2.8.0。改为官方2.8.0.post2，重新安装、导入与GPU检查；不启用跳过版本检查选项。单内核通过不能抵消集成导入失败。 |
| `imports-v4/probes/verl_vllm_async_server.json`：项目探针误要求 `vLLMAsyncServer` 属性。 | 按固定[v0.6.1源码](https://github.com/verl-project/verl/blob/v0.6.1/verl/workers/rollout/vllm_rollout/vllm_async_server.py)改为实际 `vLLMHttpServerBase / vLLMHttpServer / vLLMReplica`；这是本项目探针错误，不能算上游版本不兼容。 |
| `gpu-final/report.json`：2.8.0.post2在GPU5的BF16前反向通过，但首轮vLLM启动尝试将GPU UUID转为整数失败。 | 固定[vLLM0.10.0平台代码](https://github.com/vllm-project/vllm/blob/v0.10.0/vllm/platforms/interface.py)对可见设备条目调用int。项目保留UUID授权与初始CUDA核验，再只读NVML映射获准UUID到物理编号、核对PCI排序，仅vLLM worker改用对应数字；不改上游、不扩大设备集合。GPU5复验在 `gpu-vllm-final/report.json` 通过。 |

v4的两项导入失败均保留；修正后的 `imports-final/` 共25项（metadata+24项import）全部通过，最终204包pip check通过。双卡5/7的BF16、双向4096 bytes peer copy和16个float的NCCL all-reduce在 `gpu-pair/` 通过；GPU5的2.8.0.post2内核及0.6B单提示分别见 `gpu-final/`、`gpu-vllm-final/`，输出 `OK.`（3个token含EOS）。这些是S0正确性子集，不是吞吐或训练验收；唯一进度与完整日志索引仍在PROGRESS。

最终推理有Zig `_POSIX_C_SOURCE`重定义和上游process-group析构warning，退出0、输出有效；warning原样保留，进程清理由独立交接检查记录，不因未fatal就删去。

## FSDP2、LoRA 与多轮接口

固定 v0.6.1 的 [fsdp_workers.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/workers/fsdp_workers.py) 存在 PEFT 包装、FSDP2 与 rollout_mode 参数收集分支；[fsdp_utils.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/utils/fsdp_utils.py) 提供 apply_fsdp2 和 LoRA 参数收集。`layered_summon` 路径有基础模型预载等前提，不能把接口存在当作所有配置可用。

[vllm_rollout_spmd.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/workers/rollout/vllm_rollout/vllm_rollout_spmd.py) 的 adapter 更新包含移除旧 LoRA、TensorLoRARequest 与 add_lora；[vllm_async_server.py](https://github.com/verl-project/verl/blob/v0.6.1/verl/workers/rollout/vllm_rollout/vllm_async_server.py) 生成时检查 adapter 并传 LoRARequest。[ToolAgentLoop](https://github.com/verl-project/verl/blob/v0.6.1/verl/experimental/agent_loop/tool_agent_loop.py) 与 [AgentLoop](https://github.com/verl-project/verl/blob/v0.6.1/verl/experimental/agent_loop/agent_loop.py) 提供异步多轮及 response_mask 路径。

以上证明需要进一步验证的静态接口存在；没有证明 actor 更新的 adapter 真正在本版本组合的 rollout 使用。v0.6.1 [发布说明](https://github.com/verl-project/verl/releases/tag/v0.6.1) 还提及 CI 镜像升级到 vLLM0.11.0，不能将其视为0.10.0的背书。

## 实际证据的分层

S0必要范围验收后已生成GPU锁、工具链锁、原始安装快照和 [validation-s0.json](../requirements/validation-s0.json)，记录39项CPU测试、平台、版本、证据与未验证项。完整重建命令见 [requirements](../requirements/README.md)；第二个全新环境重装仍未实测。

快照保留FA本地wheel路径，可移植锁将其换为已核验相同bytes的官方URL与哈希；vLLM保留官方URL哈希，其余包固定版本/来源和安装RECORD摘要，未独立核验每个归档SHA256。这不是完整供应链哈希锁。FSDP2/LoRA训练、多轮adapter同步、RL更新、保存恢复与4B主实验均未验证，不能从S0锁推断通过。
