# 固定工程夹具与来源摘录

本目录保存小型可追溯输入。S1是自主编写的虚构工程夹具；S2包含固定真实metadata的研究pilot摘录和只用于quarantine的官方目标元数据索引。两者不能相互冒充，均未成为正式训练/开发/封存测试release。

| 路径 | 用途、输入输出与调用 | 阶段和验证边界 |
| --- | --- | --- |
| [s1/](s1/README.md) | 虚构办公扩展坞商品/证据、英文任务、独立真值；S1环境验收读取，也供S2 engineering配置测试流水线 | S1真实CPU工具/验证器验收已执行；不是正式训练数据或真实商品 |
| [s2/](s2/README.md) | `amazon-electronics.json`保存12条真实历史商品的原始选定列、字段/原句/单位、revision/hash；`official-exclusions.json`保存固定官方目标ID/可得品牌型号/标题，build先整品牌quarantine再split | S2真实来源获取和离线归一化已执行；官方缺品牌目标、人工审核、独立语义复核与真实教师待验收 |

CPU开发与学校Linux从项目根目录运行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-build --config configs/s2.json --output logs/my-s2-build
```

输入保持只读；SQLite、任务、轨迹、manifest/哈希和日志写入新run目录。S2事实缺失/冲突或排除导致样本减少应保留拒收原因，不能填造字段/价格或取消官方隔离来凑数量。官方索引不保存query、persona或rubrics，不能用目标metadata生成训练约束；它仅服务污染排除。商品内容不适用ECom代码MIT许可，来源许可边界见[S2来源审计](../docs/s2-source-audit.md)。

具体命令、预期产物、恢复与常见错误见[S1](../docs/stages/S1.md)及[S2](../docs/stages/S2.md)。缺文件先确认根目录；输入/数据库哈希不符按固定来源在新目录重建，保留失败证据。当前没有训练checkpoint；实际测试结果与阶段状态以[PROGRESS](../PROGRESS.md)为准。
