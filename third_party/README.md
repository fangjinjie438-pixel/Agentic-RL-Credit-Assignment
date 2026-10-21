# 固定第三方来源

`ecomagentbench/97eff345811fdf652a2135d38d874f2932e11702/` 是 EComAgentBench 的原样源码快照。`UPSTREAM-MANIFEST.json` 记录公开仓库、准确 commit、下载时间、归档 SHA256 和全部 75 个原始文件的字节数、SHA256、固定 URL。源码不作本地修改；`LICENSE`、`DATA.md`、`CITATION.cff` 随来源保留。

本项目只加载 `src/database/product_db.py` 和九个确定性工具所需模块。项目适配器位于 [upstream.py](../src/procure_rl/env/upstream.py)，加载前检查固定 SHA256；工具实际执行原生 SQLite/FTS5、过滤、详情、评论、画像、澄清和推荐代码。项目只覆盖连接工厂，强制只读/immutable 打开已提交的 split 数据库；不加载 `python_execute`、LLM、生成或官方 judge 模块。

上游 MIT 只涵盖代码；Amazon Reviews 2023 数据受原条款约束，限研究用途。本次未下载官方 26.9 GB 商品库。快照中的 `data/benchmark/benchmark.jsonl` 是官方外测资料，仅核验记录数和状态元数据，禁止用作训练、开发集、奖励设计或模型选择输入。S1 工程夹具使用本项目自建虚构商品，与官方任务无关。

CPU 开发与学校 Linux 均使用项目环境：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p test_upstream.py -v
```

实际已验证：5 项原生工具 CPU 集成测试通过，包含真实 SQL/FTS5、会话隔离、快照重放、只读与来源篡改拒绝。GPU 验证不适用；未调用教师 API。完整 S1 运行清单、阶段验收与日志由根 `PROGRESS.md` 和 `docs/stages/S1.md` 记录。

来源目录丢失时按 manifest 的固定 commit URL 恢复；校验不符时停止加载并保留失败证据，不能以 `main` 的当前版本替换。存在非空 `-wal` 或 `-journal` 时先由数据库构建流程提交、关闭并 checkpoint，再作只读访问；不要修改适配器来忽略未提交内容。更详细的 API、许可和边界见 [上游审计](../docs/ecom-upstream-audit.md)。
