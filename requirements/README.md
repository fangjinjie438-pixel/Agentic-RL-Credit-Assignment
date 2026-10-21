# 依赖候选、安装与锁定流程（S0）

| 文件 | 用途 |
| --- | --- |
| `cpu.txt` | S0 标准库零外部依赖，CPU 无需 pip 安装即可执行 |
| `gpu-candidate.in` | 待验证 GPU 直接依赖输入，Python 3.11/Linux x86_64，显式选择官方 cu126 构建与 verl commit；不是解析结果或 lock |
| `attention-candidate.in` | 独立 `flash_attn` 的官方2.8.0.post2二进制候选，CUDA12 / Torch2.7 / CPython3.11 / CXX11 ABI=True；由2.8.3导入冲突修订，最终复验见PROGRESS；不是cu126专用声明 |
| `toolchain-candidate.in` | 项目专属 `.venv-toolchain` 的 Ziglang0.17.0 编译器候选，用于Triton C launcher；与GPU包环境分开，不是系统Toolkit |
| [linux-py311-cu126-s0.lock](linux-py311-cu126-s0.lock) | S0验收后生成的学校Linux/Python3.11/cu126实际环境锁，已含FlashAttention；不代表S3/S4通过 |
| [toolchain-s0.lock](toolchain-s0.lock) | 已生成的项目Zig编译器环境锁，只用于 `.venv-toolchain` |
| [installed-snapshot.txt](installed-snapshot.txt) | 原始实装快照，保留FlashAttention本地wheel路径；不能单独当兼容性证据 |
| [validation-s0.json](validation-s0.json) | 机器、实装版本、证据、S0范围、未验证项、锁哈希与来源转换说明 |

静态来源、wheel 元数据和接口依据见 [依赖审计](../docs/dependency-audit.md)。CPU 工具支持 Python 3.10+；GPU 候选固定 3.11。不要向系统 Python 或既有共享 conda 环境安装。下载 wheel、静态解析不需要占用 GPU；GPU 计算仍须先确认本次设备。

## CPU 开发（学校和本机）

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv python install 3.11 --no-bin
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11 .venv-cpu
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

学校的实际解释器路径和已验证命令见 S0。源码可支持3.10，但本项目执行全部使用项目独立3.11，不使用系统/共享 Python 或 Toolkit。CPU 运行不导入 ML 库。

## 从S0实际锁重建

S0声明范围已验收；从锁重建优先于重新解析候选。以下从项目根目录为**不存在的新虚拟环境**重建GPU与工具链，固定本轮Python3.11.16；现有环境不要直接清空，`uv pip sync`会移除目标环境中不在锁内的包。第二个全新环境重装尚未实测，重建后须重新保存pip check、导入与获准设备的GPU报告。

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv python install 3.11.16 --no-bin
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11.16 .venv-gpu
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11.16 .venv-toolchain
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip sync --python .venv-gpu/bin/python --only-binary :all: --no-binary verl --no-binary pylatexenc --no-binary antlr4-python3-runtime requirements/linux-py311-cu126-s0.lock
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip sync --python .venv-toolchain/bin/python --only-binary :all: requirements/toolchain-s0.lock
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip check --python .venv-gpu/bin/python
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip check --python .venv-toolchain/bin/python
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-environment --output logs/my-rebuilt-imports --python .venv-gpu/bin/python --timeout 120
```

最后一条使用既有项目CPU环境；新机器先按上节建立它。GPU锁已包含FlashAttention，**不再额外安装attention候选**。仅verl、pylatexenc、ANTLR三个纯Python包允许源码构建，其余仅二进制；网络问题可按下节给单条命令套代理。编译器包装器和driver-only链接沿用S0约定，真实GPU命令仍需本次授权。

原始快照保留实装FlashAttention的 `file://` 来源；可移植GPU锁把它替换为已核验相同bytes的官方URL与SHA256，并保留vLLM官方URL哈希。其他包固定版本/直接来源并记录安装RECORD摘要，**没有逐包独立验证全部归档哈希**；不要把它称为完整供应链哈希锁，也不要对当前文件直接启用要求每项都有哈希的 `--require-hashes`。

## 学校 Linux GPU 候选

下列流程用于有理由修改候选时重新解析，恢复本轮环境使用上一节实际锁。候选输入不是lock；不安装到 `.venv-cpu`，不自动改换核心版本。下载前检查磁盘配额和缓存位置；已有环境无需重建，输出目录须新的。

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11 .venv-gpu
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip compile --python .venv-gpu/bin/python --only-binary :all: --no-binary verl --no-binary pylatexenc --no-binary antlr4-python3-runtime requirements/gpu-candidate.in --output-file requirements/gpu-resolved-candidate.txt
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip install --python .venv-gpu/bin/python --only-binary :all: --no-binary verl --no-binary pylatexenc --no-binary antlr4-python3-runtime -r requirements/gpu-resolved-candidate.txt
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip check --python .venv-gpu/bin/python
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-environment --output logs/my-environment --python .venv-gpu/bin/python --timeout 120
```

`gpu-resolved-candidate.txt`仅在解析成功后出现，仍不代表GPU通过。构建白名单限定审阅后的纯Python verl、pylatexenc、antlr4-python3-runtime，其余只用二进制；不放开CUDA扩展源码构建。

本轮解析产物放在 `logs/s0-20261022T0145+0800/dependencies/`，v2/v3/v4和失败均保留。实际导入暴露Arrow/NumPy和Hydra/OmegaConf等API问题后，固定PyArrow19.0.1、Datasets3.6.0、Pandas2.2.3、Hydra1.3.2、OmegaConf2.3.0、ANTLR4.9.3、Setuptools78.1.0；四个核心版本保持不变。错误、官方依据与实际结果见[审计](../docs/dependency-audit.md)，最终验收见PROGRESS。

固定 vLLM 官方 cu126 wheel，不能用默认 PyPI 的 cu128 构建替代；Torch / TorchVision / TorchAudio / xformers 均使用明确的官方cu126 wheel URL，其余包走PyPI，避免全局额外索引把普通包导向Torch索引。PEFT0.16.0、Accelerate1.8.1、TorchData0.11.0是新增候选，须记录实际解析版本与导入结果。最终下载还需核对文件哈希，网页资产声明不等于本地文件已校验。

网络有问题时，用户已授权 `proxy_on`。可对单条命令使用项目包装器，例如：

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" .venv-cpu/bin/python scripts/with_proxy.py -- uv pip compile --python .venv-gpu/bin/python --only-binary :all: --no-binary verl --no-binary pylatexenc --no-binary antlr4-python3-runtime requirements/gpu-candidate.in --output-file requirements/gpu-resolved-candidate.txt
```

包装器仅读取独立 `proxy_on` 函数，不 source 整个shell初始化、不输出凭据；具体说明见 [scripts](../scripts/README.md)。网络失败与依赖冲突分别报告。

## 独立编译器与 FlashAttention

Triton运行时可能编译C launcher。为遵守项目工具隔离约束，使用 `.venv-toolchain`，不把编译器加入CPU零依赖环境，不调用系统GCC/nvcc：

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11 .venv-toolchain
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip install --python .venv-toolchain/bin/python --only-binary :all: -r requirements/toolchain-candidate.in
scripts/toolchain/cc --version
scripts/toolchain/cxx --version
CUDA_VISIBLE_DEVICES='' .venv-gpu/bin/python -c 'import torch; print(torch.__version__, torch.version.cuda, torch._C._GLIBCXX_USE_CXX11_ABI)'
```

实际Torch的CXX11 ABI为True，证据在本轮 `dependencies/torch-abi.json`。FlashAttention使用CUDA12/Torch2.7/ABITrue构建，不能称“cu126专用”。2.8.3被xformers0.0.31拒绝后，已修订为官方2.8.0.post2，隐藏GPU导入与真实内核复验通过；没有跳过版本检查。`vllm.vllm_flash_attn`与训练侧独立 `flash_attn` 分别验证。以下只用于候选重新安装，实际锁重建无需重复：

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip install --python .venv-gpu/bin/python --no-deps --only-binary :all: -r requirements/attention-candidate.in
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv pip check --python .venv-gpu/bin/python
```

GPU预检自动把CC/CXX指向项目包装器，把驱动查找指向项目 `.tools/cuda-driver/lib`，并清理共享环境注入。该目录只链接必要的系统NVIDIA驱动库，不是CUDA Toolkit；实际准备记录见本轮 `driver-links.json`。`.tools/cuda` 尚无Toolkit时，源码CUDA扩展应明确失败，不能回落 `/usr/local/cuda`。

## 验证与锁定门槛

1. 保存解析、安装与 `pip check` 的完整日志、退出码；逐项报告，不把网络失败叫作依赖不兼容。
2. 记录当前 Python、glibc、包版本与实际 verl commit。CPU 导入测试独立于安装状态；本阶段默认 doctor 不导入 GPU 库。
3. 具体 GPU 归属确认后，用已实现的 `gpu-probe` 在限制设备的独立进程验证 Torch CUDA/BF16、实际runtime/NCCL、双卡P2P/NCCL、独立FlashAttention和单卡vLLM；完整命令见S0。用户已授权GPU5/7，GPU4仅只读。S3–S4再验真实多轮与actor→rollout LoRA同步。
4. 环境达到相应验收级别后，才生成注明平台/日期/验证范围的实际环境锁及 wheel 哈希清单，保留候选和完整失败记录。`pip freeze` 快照单独保存为 `installed-snapshot.txt`，不能单凭快照声明全栈兼容。

实际锁已在S0必要验收后生成，范围及证据见 `validation-s0.json` 与PROGRESS。S0没有checkpoint；重建后仍需对应机器复验。多轮LoRA同步、FSDP2训练、RL更新与保存恢复均未验证；不修改系统CUDA，CUDA源码扩展需另建项目Toolkit后验收。

