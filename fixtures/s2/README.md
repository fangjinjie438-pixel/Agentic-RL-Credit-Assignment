# S2 真实来源 pilot

当前真实构建配置使用 `official-exclusions-candidate.json`：在原索引上加入 3 个缺 Brand 目标由 store/Manufacturer/title 交叉佐证的保守排除别名（Alphaline、EtherealKiller、Reolink Digital）。它只扩大 quarantine，未补造原始 Brand 或人工确认，仍为 `metadata_complete=false`。可复用审计入口 `scripts/data/audit_official_identities.py`；证据在 `logs/s2-official-identity-audit-20261022-v2/`。原 `official-exclusions.json` 保留不变供追溯。

`amazon-electronics.json` 是 Amazon Reviews 2023 固定 HF revision `2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e` 的 12 条真实商品摘录，含原始选定列、原始记录哈希、显式原字段/原句/数值/单位。它不是 S1 虚构夹具；也不是已验收可发布的正式训练集。该元数据的价格为采集时的美元价格，不代表当前报价。用途仅为本项目研究 pilot，数据不能套用 ECom 代码的 MIT 许可。来源与传输证据见 [审计](../../docs/s2-source-audit.md)。

`official-exclusions.json` 从固定官方 benchmark 只访问 `target_product` 的商品 ID、标题、Brand 与明确的 Item model number/Model Number，用于 quarantine。662 条任务得到 660 唯一 ID、660 标题、558 整品牌 family、420 品牌型号组合；同品牌全体保守排除，不把官方目标元数据写进任务表达。`coverage=target_ids_and_available_brand_model_title`：3 个官方目标缺品牌，其家族仍未知，因此 `metadata_complete=false`。没有访问 query、persona 或 rubrics。原 ID-only 版本保留在 `logs/s2-source-audit/official-exclusions-id-only.json`。当前12条来源中 Logitech/Samsung/Dell/HP 四条按整品牌隔离，余8条进入 split；exact-ID 本身没有重叠。官方污染隔离仍需补齐缺品牌目标与人工/独立语义审核。

来源字段存在局限：12 条均有明确价格和重量；8 条有可信颜色字段供 price/color/weight 模板。HP `Non-Touchsceen`、Mafiti 键盘组合描述虽出现在原始 Color 中，因语义不是颜色而没有转成颜色事实。部分来源规格可能含营销误标，保留原文进入人工核验；不从标题补价格或规格。品牌全部来自结构化 `details.Brand`，家族默认整品牌保守分组并标记 `identity_review_required`，尚未经人工签核。

离线 CPU 开发 / 学校 Linux 验证相同：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_data_sources.py' -v
```

输入固定 JSON，输出 unittest 结果；测试包含真实来源归一化→S1 SQLite 只读访问与可用官方目标元数据隔离。**实际已验证：真实来源抽取、归一化与只读 SQLite 检查；扩充官方目标元数据后的最终测试结果以根 PROGRESS 的正式日志为准。** 不访问网络、模型、教师或 GPU。首次原始来源获取使用 [独立提取脚本](../../scripts/data/README.md)，普通离线流水线不依赖 PyArrow。原始摘录只读；恢复时保留失败运行目录，按固定 revision 重新读取，换新输出目录，不自动换数据版本。正式 S2 的任务构建、split、反事实及采集流程见阶段文档。
