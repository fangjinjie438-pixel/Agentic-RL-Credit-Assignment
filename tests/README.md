# 测试目录

本目录的测试均为 CPU 测试，只使用项目独立解释器与 `.venv-cpu`，不调用系统或共享 Python/Toolkit。
不下载模型、不访问教师 API、不创建 CUDA 上下文。doctor 的系统 Toolkit 信息仅列路径与符号链接元数据，策略为 `no_toolkit_execution`。
通过这些测试仅说明对应本地行为通过，不能证明候选依赖兼容或真实 GPU 训练通过。

| 文件 | 用途与输入输出 | 关联阶段 | 执行方式 |
| --- | --- | --- | --- |
| `test_doctor.py` | mock 只读 NVIDIA/Git 探测，检查缺失工具、失败退出码、超时、禁止运行系统 Toolkit、GPU 分配边界和 JSON/Markdown 产物；输出 unittest 结果 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_doctor.py' -v` |
| `test_config_runtime.py` | 检查候选配置、版本与设备分配边界；验证运行清单、失败日志、源码哈希和拒绝覆盖已有证据 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_config_runtime.py' -v` |
| `test_environment_probe.py` | mock ML 导入与子进程，检查项目解释器限定、GPU隐藏、离线模式、metadata/commit记录、超时/失败不误报，以及禁止子进程执行编译器/Toolkit；输出 unittest 结果 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_environment_probe.py' -v` |
| `test_gpu_probe.py` | mock GPU worker 与临时JSON结果，检查默认dry-run无ML导入、完整UUID/来源门禁、单卡模型限制、环境清理/缓存隔离、超时及通信异常回收、运行时UUID核验，以及vLLM的只读UUID/PCI索引映射和失败拒绝 | S0 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_gpu_probe.py' -v` |
| `test_upstream.py` | 在独立虚构 SQLite 上实际执行固定上游九个工具，检查 FTS 搜索、过滤、详情/评论/推荐、只读无 sidecar、原生澄清快照与并发隔离，以及源码篡改和未提交 WAL 拒绝；无工具 mock，输出 unittest 结果 | S1 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_upstream.py' -v` |
| `test_verifier.py` | 输入小型任务、事实、证据和独立预期，检查多合法解、分项硬约束、事实终局奖励与证据交付分离、伪造/重复证据、布尔/数值类型、首次覆盖预算与防刷分、输入不变；纯 CPU 数值验证 | S1 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_verifier.py' -v` |
| `test_data_sources.py` | 检查S2原始字段/原句/哈希、单位/币种/冲突拒收，12条真实pilot归一化→只读SQLite与官方660个ID及可得品牌/型号/标题quarantine边界；无网络/API/GPU | S2 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_data_sources.py' -v` |
| `test_data_split.py` | 14项家族/型号/近重复连通、MinHash/Jaccard边界、输入顺序/种子稳定、官方整簇隔离、任务兄弟与证据split审计、语义候选限制 | S2 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_data_split.py' -v` |
| `test_data_teacher.py` | 16项观测隐私、真实本地HTTP请求/响应/工具ID、缓存/预算/恢复、原始错误响应去密、未完成计费请求拒重试、回放篡改拒收与工程隔离；外部教师未调用 | S2 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_data_teacher.py' -v` |
| `test_data_builder.py` | 13项独立可行解/反事实/改写、字面泄漏、全split解集、审核拒收与冲突、raw原始行绑定、封存开关，以及真实来源→SQLite→观测脚本→回放→发布门槛端到端 | S2 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_data_builder.py' -v` |
| `test_session.py` | 使用 `fixtures/s1` 构建真实 split SQLite，并执行原生工具/会话；与独立规格真值矩阵比较七个候选，验证隐藏信息、快照重放/篡改/跨配置拒绝、并发隔离、只读检索、预算、非法/深层 JSON/非有限输入、防刷分与结构化轨迹 | S1 | `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_session.py' -v` |

在项目根目录执行所有当前测试：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv-cpu/bin/python scripts/run_cpu_tests.py --stage S2 --config configs/s2.json --output logs/my-s2-tests
```

S1 还提供保存数据库、轨迹、快照与运行清单的完整环境验收，使用新输出目录：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
```

**实际已验证：**[S1 验收报告](../logs/s1-20261022/acceptance-final/report.json) 为 27/27 项通过，覆盖真实 CPU SQLite/上游工具/项目环境。当前代码包括 S0 原 39 项与 S1 新 43 项（upstream 5、verifier 21、session 17），全量最终通过、失败和跳过数量以根 `PROGRESS.md` 的正式日志为准。该验收使用协作 agent 编写并逐项核对的虚构规格和独立预期矩阵，没有额外人工签核，也不是模型任务成功率。

S2 最终全量结果：**136项，0失败/错误/跳过**，S0/S1原82 + S2新增54（sources11、split14、teacher16、builder13）。原始日志与runner/测试/fixture/source哈希在 [tests-v1](../logs/s2-20261022/tests-v1/run.json)。本地HTTP测试需执行上下文允许临时loopback socket；无外部模型/教师/GPU。两种来源的最终工程脚本各2/2通过真实回放、专家候选0，详见S2/PROGRESS；真实教师和人工/8B审核仍未执行。

上面的命令只使用项目独立 `.venv-cpu`；独立解释器与环境创建方式见根目录 README，禁止替换为系统 `python3`。
实际执行证据以根目录 `PROGRESS.md` 和其中的日志位置为准；新规则前的系统工具探测若被保留，只能标为历史证据。
真实 GPU 预检入口位于 `src/procure_rl/gpu_probe.py`，完整执行方式见 [S0](../docs/stages/S0.md)。本目录测试不执行它的计算路径；实际 CUDA、双卡 P2P/NCCL、独立 FlashAttention 与 vLLM 结果分别由运行报告证明。真实多轮 LoRA 同步与训练仍属于 S3/S4，不能由本目录测试替代。

若出现 `ModuleNotFoundError: procure_rl`，确认从项目根目录运行并设置 `PYTHONPATH=src`。
新增测试文件时必须同步本表；不要把 mock 或本地测试写成学校 GPU 验证通过。
unittest 在临时目录生成并自动清理 SQLite，输出测试结果，不保存 checkpoint；持久证据由 `s1-smoke` 写入新运行目录。输出目录已存在时更换目录，失败日志和快照保留用于排错。测试通过不代表官方完整数据/LLM judge、真实模型多轮推理或 S3/S4 训练验收通过。
