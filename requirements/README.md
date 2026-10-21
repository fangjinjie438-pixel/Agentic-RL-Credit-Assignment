# 依赖候选、安装与锁定流程（S0）

| 文件 | 用途 |
| --- | --- |
| `cpu.txt` | S0 标准库零外部依赖，CPU 无需 pip 安装即可执行 |
| `gpu-candidate.in` | 待验证 GPU 直接依赖输入，Python 3.11/Linux x86_64，显式选择官方 cu126 构建与 verl commit；不是解析结果或 lock |

静态来源、wheel 元数据和接口依据见 [依赖审计](../docs/dependency-audit.md)。CPU 工具支持 Python 3.10+；GPU 候选固定 3.11。不要向系统 Python 或既有共享 conda 环境安装。下载 wheel、静态解析不需要占用 GPU；GPU 计算仍须先确认本次设备。

## CPU 开发（学校和本机）

```bash
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv python install 3.11 --no-bin
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" uv venv --managed-python --python 3.11 .venv-cpu
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

学校的实际解释器路径和已验证命令见 S0。源码可支持3.10，但本项目执行全部使用项目独立3.11，不使用系统/共享 Python 或 Toolkit。CPU 运行不导入 ML 库。

## 学校 Linux GPU 候选（尚未验证）

以下是**待执行流程**；是否实际执行过某步以 PROGRESS 和日志为准。隔离环境解析先行，不安装到 `.venv-cpu`，也不自动改换候选矩阵。GPU 大包下载前检查项目磁盘配额和缓存位置。

```bash
UV_CACHE_DIR="$PWD/.cache/uv" uv venv --python .venv-cpu/bin/python .venv-gpu
UV_CACHE_DIR="$PWD/.cache/uv" uv pip compile --python .venv-gpu/bin/python --no-build requirements/gpu-candidate.in --output-file requirements/gpu-resolved-candidate.txt
UV_CACHE_DIR="$PWD/.cache/uv" uv pip install --python .venv-gpu/bin/python -r requirements/gpu-resolved-candidate.txt
UV_CACHE_DIR="$PWD/.cache/uv" uv pip check --python .venv-gpu/bin/python
```

`gpu-resolved-candidate.txt` 仅在解析成功后出现，仍不代表 GPU 通过。`--no-build` 避免解析阶段执行未知构建；如固定 verl 的元数据必须构建才能解析，先检查上游构建配置并记录，再决定受控构建步骤，不直接去掉约束掩盖问题。

本轮已在固定 commit 检查 `setup.py` / `pyproject.toml`，允许纯 Python verl 与 pylatexenc 元数据构建的实际命令见 S0；其他包保持仅二进制。各次命令输出及是否成功以 PROGRESS 为准。

固定 vLLM 官方 cu126 wheel，不能用默认 PyPI 的 cu128 构建替代；torch / torchvision / torchaudio 均显式 `+cu126`，xformers 也固定官方 cu126 来源。新增 PEFT/Accelerate/TorchData 等传递依赖须记录解析版本并检查与 Transformers 4.53.2 的关系，不通过放宽本项目核心版本消除冲突。最终下载还需核对文件哈希，网页资产声明不等于本地文件已校验。

## 验证与锁定门槛

1. 保存解析、安装与 `pip check` 的完整日志、退出码；逐项报告，不把网络失败叫作依赖不兼容。
2. 记录当前 Python、glibc、包版本与实际 verl commit。CPU 导入测试独立于安装状态；本阶段默认 doctor 不导入 GPU 库。
3. 具体 GPU 归属确认后，在限制设备的独立进程验证 Torch CUDA/BF16、实际 runtime/NCCL、单卡 vLLM 和多卡 P2P/NCCL；S3–S4 再验真实多轮与 actor→rollout LoRA 同步。命令和代码按阶段实现，不虚构当前不存在的 GPU 验证脚本。
4. 环境达到相应验收级别后，才生成注明平台/日期/验证范围的实际环境锁及 wheel 哈希清单，保留候选和完整失败记录。`pip freeze` 快照单独保存为 `installed-snapshot.txt`，不能单凭快照声明全栈兼容。

当前没有已验证 GPU lock。没有 checkpoint；CPU 工具直接重跑，GPU 环境重建应使用后续实际验证的锁定输入。不修改系统 CUDA；PATH 中找不到 nvcc 不代表预编译 wheel 必须安装系统 Toolkit，源码 CUDA 扩展的构建需求需另行核查。

