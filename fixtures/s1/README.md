# S1 虚构扩展坞夹具

固定 revision 为 `s1-fixture-v1`，包含 9 件虚构商品、45 条明确证据、2 个英文任务。全部内容由项目自主编写，价格和规格是工程事实，不代表真实商品能力。`official_test` 与 `sealed_test` 两件商品仅检查 split 隔离；它们不是官方任务、真实官方目标商品或 S2 封存测试数据。

| 文件 | 用途、输入输出及调用关系 | 验证状态 |
| --- | --- | --- |
| `catalog.json` | 输入商品事实；每件商品包含唯一 ID、独立家族、split、价格、结构化规格与证据。环境构建入口为每个 split 写入物理独立的 SQLite 文件，运行时只读打开任务所属文件 | JSON、引用与独立事实一致性检查已执行；真实环境验收 27/27 通过，见下方报告 |
| `tasks.json` | 输入 `task-train-dual` 与 `task-dev-dual`；显性预算来自 query，接口来自 persona，双屏与至少 65 W 的要求来自两次确定性澄清；会话/验证器读取约束及证据引用 | 引用仅包含任务同 split、同字段的支持与反证；初始 query/persona 未写入隐藏要求 |
| `expectations.json` | 独立预期矩阵；记录每个候选的四项约束真假、合法解集合、反例原因及隔离专用商品。只供验收使用，不注入 Agent observation | 协作 agent 按独立列出的规格真值逐项核对，未调用项目验证器生成期望结果；没有额外人工签核 |

任务均要求预算不超过 150 USD、USB-C 主机接口、至少两台同时使用的外接显示器、主机供电至少 65 W。所有商品的供电证据仅由 `reviews` 返回；预算、接口、屏幕数量与重量在 `details`。取得真实工具证据与事实满足约束是独立的验收维度；拿到错误候选的反证仍可构成新的相关证据。

| split / 任务 | 商品 | 规格真值结论 |
| --- | --- | --- |
| train / `task-train-dual` | `dock-train-a` | 119 USD / USB-C / 2 屏 / 90 W，合法 |
| train / `task-train-dual` | `dock-train-b` | 139 USD / USB-C / 2 屏 / 65 W，合法；验证边界值与多合法解 |
| train / `task-train-dual` | `dock-train-one` | 99 USD / USB-C / 1 屏 / 90 W，仅 `displays` 不满足 |
| train / `task-train-dual` | `dock-train-low` | 109 USD / USB-C / 2 屏 / 45 W，仅 `power` 不满足 |
| dev / `task-dev-dual` | `dock-dev-a` | 129 USD / USB-C / 2 屏 / 85 W，合法 |
| dev / `task-dev-dual` | `dock-dev-expensive` | 179 USD / USB-C / 2 屏 / 100 W，仅 `budget` 不满足 |
| dev / `task-dev-dual` | `dock-dev-legacy` | 89 USD / USB-A / 2 屏 / 90 W，仅 `interface` 不满足 |
| sealed_test / 无任务 | `dock-sealed-a` | 独立 Poppy 家族，只用于证明 train/dev 无法读取 |
| official_test / 无任务 | `dock-official-a` | 独立 Aster 家族，只用于证明 train/dev 无法读取；不是官方 benchmark 数据 |

CPU 开发与学校 Linux 使用同一项目独立解释器，无 GPU、模型下载或教师 API。JSON 解析命令如下，均从项目根目录运行：

```bash
.venv-cpu/bin/python -m json.tool fixtures/s1/catalog.json > /dev/null
.venv-cpu/bin/python -m json.tool fixtures/s1/tasks.json > /dev/null
.venv-cpu/bin/python -m json.tool fixtures/s1/expectations.json > /dev/null
```

预期均退出 0，无持久输出。完整 SQLite 构建、工具执行、快照回放与验收使用：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v
```

**实际已验证：**[S1 CPU 验收报告](../../logs/s1-20261022/acceptance-v1/report.json) 记录 27/27 项通过，包含七个候选的规格真假比较与快照重放、并发和 split 隔离、预算及只读数据库检查。报告保存三个 JSON 的 SHA256；数据库、轨迹与终局前快照保存在同一运行目录。配置、预期产物、恢复与排错完整说明见 [S1](../../docs/stages/S1.md)，全量 unittest 最终结果以根 `PROGRESS.md` 为准。该结果不代表完整官方数据库/LLM judge、模型推理、GPU 或训练通过；这里的脚本轨迹不是专家示范数据。

恢复时保留原始 JSON，换新输出目录重建 SQLite，不覆盖先前证据。若读到其他 split 的商品则视为隔离失败；若证据 ID 不存在，检查本目录三个文件是否来自相同 revision。扩大任务数量、改写生成和真正的数据集划分属于 S2，不在本夹具中进行。
