# S1 环境与验证器

本目录用固定版本 EComAgentBench 的真实 CPU 工具执行采购会话，并提供项目新增的 split 隔离、预算、证据、快照与确定性验证。仅使用 Python 标准库和 SQLite FTS5；不加载模型、教师 API、官方评测任务或 GPU 库。固定上游 commit 为 `97eff345811fdf652a2135d38d874f2932e11702`，来源与许可见 [上游副本](../../../third_party/ecomagentbench/97eff345811fdf652a2135d38d874f2932e11702/README.md)及 [S1 操作文档](../../../docs/stages/S1.md)。

| 文件 | 用途、主要输入输出及调用关系 | 阶段与入口 |
| --- | --- | --- |
| `__init__.py` | 导出 `Catalog`、`build_catalog`、`load_tasks`、`ProcurementEnv`、`StepResult`；导入项目接口，不启动模型或 GPU | S1；供调用方导入，无独立命令 |
| `catalog.py` | `build_catalog` 读取有 revision 的商品 JSON，校验证据与家族边界，向新目录写四个物理独立的 split SQLite 文件及 SHA256 manifest。`Catalog` 核对所选文件哈希，以 `mode=ro&immutable=1` 和 `query_only` 提供私有事实与证据；`load_tasks` 校验工程任务、澄清映射与预算 | S1；由 `smoke.py` 构建，由 `session.py` 读取 |
| `upstream.py` | 校验固定 commit 的 11 个源文件 SHA256，隔离加载上游九个工具。输入单个 split 数据库、画像与澄清脚本，输出原生 schema/工具字典；只替换数据库连接为只读连接。每个实例独立保存澄清次数与揭示标志，并提供原生状态快照/恢复/关闭 | S1；由 `ProcurementEnv.reset/step` 调用；不启用上游 `python_execute` |
| `protocol.py` | `parse_action` 接收 `{name, arguments}` 字典或 JSON 字符串，按工具 schema 校验名称、必填字段、类型、长度、有限数值、重复键与未知字段；返回规范动作，非法输入转换为 `ActionError` | S1；由 `session.py` 调用，无代码执行工具 |
| `session.py` | `ProcurementEnv` 将私有任务与单个 split `Catalog` 绑定；`reset/step` 输出可见 observation，`StepResult` 另含奖励与审计。维护步数、澄清状态、首次覆盖、调用指纹、RNG、历史及终局；`snapshot/restore` 通过哈希和确定性重放校验后恢复，`trajectory` 导出结构化轨迹 | S1；供 `smoke.py` 与后续 rollout 适配层调用 |
| `verifier.py` | `verify_final` 接收私有任务/商品事实、最终提交和已观察证据，独立计算硬约束真假、终局奖励与交付诊断；`process_events` 从真实 observation 的结构化揭示/证据生成首次覆盖事件和有界过程分数。纯函数，不修改输入、不解析日志或调用 LLM | S1；由 `session.py` 调用，独立数值测试覆盖 |
| `smoke.py` | `run_smoke` 读取 S1 配置与固定 JSON，在新运行目录构建 SQLite，执行七条候选轨迹、终局前快照重放、并发隔离、无效/重复调用与预算检查；对照独立预期矩阵，输出报告、轨迹、快照及数据库 manifest | S1；CLI `s1-smoke` 调用 |

上游工具为 `search_products`、`filter_by_attribute`、`get_product_details`、`get_review_content`、`get_product_review_stats`、`get_store_products`、`get_user_profile`、`ask_user`、`recommend_product`。最终工具保留原生 `product_id/reasoning`，增加项目 `checks` 证据引用；会话将事实核验字段传给终局验证器。供电等 review 专属事实必须由真实评论检索返回对应原句后才附证据，不因请求商品 ID 自动揭示。

初始 observation 仅有 query 及其约束；画像和澄清约束分别在对应工具执行后出现。只有 `reset` 返回值、`StepResult.observation` 与工具 schema 可进入 Agent prompt；`StepResult` 的奖励、`terminal_validation`、事件、完整任务、商品私有事实、快照与轨迹均为审计状态，不能作为隐藏答案提供给 Agent。`turn_spans` 在 S1 为空，尚未进行 token 化或训练适配。

`success` 与 `terminal_reward` 严格采用 PLAN 的 baseline：推荐商品真实满足全部硬约束且未耗尽预算，奖励为 1；错误商品、未完成或预算耗尽为 0。`delivery_success` 另外要求需求已揭示、逐项 checks 完整，且引用确实观察过、与推荐商品/字段绑定的合法证据。提前猜中合法商品可能获得事实终局奖励，同时交付诊断失败；缺证据不改变 baseline 定义。首次隐藏需求总正预算为 0.4，首次相关约束证据总正预算为 0.6；重复事实和更换候选不能刷新该预算，无效调用扣 0.05，重复且无进展扣 0.02。

主任务预算为 40 次工具调用，压力测试上限为 80；加载器允许 1–80，较小值用于边界验收。澄清最多 10 次，按任务配置可更少；无效动作也消耗总步数。结束后 `step` 拒绝继续，须 `reset`；离线分支可恢复终局前快照。恢复时核对任务、数据库、策略与 schema，并重放动作比较完整状态；不能跨配置强行恢复。

CPU 开发与学校 Linux 均从项目根目录使用项目独立解释器，已有 `.venv-cpu` 无需重建：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

配置 `configs/s1.json` 指向 `fixtures/s1`、策略版本 `scripted-s1-v1`、种子 0。预期验收退出 0，输出 `report.json/report.md`、`catalog/manifest.json` 与四个 SQLite 文件、`trajectories/` 中七条轨迹及终局前快照、`concurrent.json`、`budget-and-invalid.json`，CLI 同时保存 `run.json/run.log` 与配置/源码哈希。输出目录必须是新的；失败时保留原始产物，换目录重跑，不覆盖证据，也没有模型 checkpoint 需要恢复。

**实际已验证：**学校 Linux 的 [acceptance-final/report.json](../../../logs/s1-20261022/acceptance-final/report.json) 记录 27/27 项 CPU 环境验收通过，数据 revision 为 `s1-fixture-v1`，Python 3.11.16；运行使用真实 SQLite 与固定上游工具。全量 unittest 最终数量与日志以 [PROGRESS](../../../PROGRESS.md) 为准。完整官方商品库/LLM judge、80 步压力任务、真实模型多轮推理、GPU、LoRA 与训练均不在该报告的验证范围。

出现 `ModuleNotFoundError` 时确认当前目录和 `PYTHONPATH=src`；缺少 SQLite FTS5 时数据库构建会失败，不能换成空搜索结果冒充成功。源码校验失败时恢复固定上游副本；数据库哈希不符或有未提交 WAL/journal 时，从固定 JSON 在新运行目录重建。快照重放不符时保留失败快照/轨迹，检查数据与策略版本，不绕过校验。每个会话完成后调用 `close` 释放只读连接。
