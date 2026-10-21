# S1 EComAgentBench 上游核验

核验日期：2026-10-22（Asia/Shanghai）。本次只实现 S1 的 CPU 环境与验证器；没有调用教师 API、下载模型或运行 GPU。

## 版本与来源证据

公开仓库是 [Morizeyao/EComAgentBench_](https://github.com/Morizeyao/EComAgentBench_)。通过已授权的单命令代理执行：

```bash
.venv-cpu/bin/python scripts/with_proxy.py -- git ls-remote https://github.com/Morizeyao/EComAgentBench_.git refs/heads/main
```

实得 commit：`97eff345811fdf652a2135d38d874f2932e11702`。GitHub 网页搜索缓存曾展示旧 commit `867dcc5`，因此未据缓存锁版本。GitHub REST API 首次在沙箱内因网络权限失败，使用允许网络的执行上下文后返回匿名限流 HTTP 403；`git ls-remote` 及固定 commit 的 codeload 下载成功，无残留访问阻塞。

固定[源码归档](https://codeload.github.com/Morizeyao/EComAgentBench_/tar.gz/97eff345811fdf652a2135d38d874f2932e11702)下载 1,242,679 bytes，SHA256 `df5c96b2de11f336ac5c2a90a6a547286765fc96c1d956419b327fa96ecdfcd3`。解包 75 个文件共 6,446,800 bytes，均原样保留于 `third_party/ecomagentbench/<commit>/`。逐文件 URL、SHA256、字节数与下载 UTC 时间见 `UPSTREAM-MANIFEST.json`；全部 75 个文件已按 manifest 复核一致。归档字节的哈希已记录，归档本身未额外保留；可按固定 URL 重新下载。

发布的 `data/benchmark/benchmark.jsonl` 是 6,039,017 bytes，SHA256 `c6585d7adade0bf898dcc6b5377fb4534a699b874bd21ec796acfa96547c9b52`。本次只读取计数和 `sample_status` 元数据：662 条均为 `ok`。未取官方 target/rubrics 来设计项目约束、奖励或夹具。

## 许可证与数据边界

固定版本的 [LICENSE](https://raw.githubusercontent.com/Morizeyao/EComAgentBench_/97eff345811fdf652a2135d38d874f2932e11702/LICENSE) 为 MIT，并明确该许可仅适用代码；原样保留版权声明与免责声明。上游 `DATA.md` 说明商品来源为 Amazon Reviews 2023，适用其原始研究用途条款；画像与澄清由 LLM 合成。没有将 MIT 扩展为商品数据许可。

上游 [HF 商品库](https://huggingface.co/datasets/ecomagentbench/EcomAgentBenchProductDB) 的卡片说明原库约 3.7M 商品、21.4M 评论、26.9 GB，获数据作者允许作研究评测。本次不下载该大文件，不声称已运行完整官方商品环境。S1 使用本项目自建虚构办公扩展坞、独立 split 数据库和结构化事实；它是实际原生工具集成的工程夹具，不是正式训练集或官方分数。

官方 662 条任务及其目标商品/近重复家族保持外测边界，不能进入训练、开发调参、奖励修改或 checkpoint 选择。未来官方评测需要固定 HF revision、下载 SHA256、原始数据条款及原始 judge 运行证据，本次未执行。

## 原生 CPU API 与项目适配

上游没有 `reset/step/snapshot/restore` 会话接口；`ShoppingAgent.run()` 自己维护交互循环且依赖 `LLMClient`。本项目不导入该循环。实际复用原生 `ProductDB` 查询方法、`BaseTool` 与下列九个工具；工具结果保持原字典结构，项目 session 负责预算、终止、证据 ID、确定性评分与统一日志。

| 工具名称 | 原生参数 | 原生输出要点 |
| --- | --- | --- |
| `search_products` | `query: str`, `page: int = 0` | `products`（ID/标题）、`page`、`total_found`；标题 FTS5/BM25，每页最多 20 |
| `filter_by_attribute` | `product_ids: list[str]`、`attribute_name: str`、`attribute_value: str` | `product_ids`；最多 10，规范 key 忽略大小写、值作子串匹配 |
| `get_product_details` | `product_id: str` | `product` 的价格、details、features 等；不含评论与 rating |
| `get_review_content` | `query: str`、`product_id: str` | 商品内评论 FTS5，最多 5 条 rating/title/text |
| `get_product_review_stats` | `product_ids: list[str]` | 最多 10 个商品的平均 rating 和样本数 |
| `get_store_products` | `store_name: str`、`page: int = 0` | 精确店名，分页 ID/标题 |
| `get_user_profile` | 空对象 | 配置的 `profile`，无 LLM 调用 |
| `ask_user` | `question: str` | `user_response`、`turns_remaining`；确定性关键词匹配 |
| `recommend_product` | `product_id: str`、`reasoning: str` | `recommended_product`（有效 ID/标题或 `None`）、`reasoning` |

原生第十个工具 `python_execute` 在本项目不注册、不导入、不提供 schema。其源码仍原样保留以满足来源完整性；S1 无需任意 Python 执行能力。原生 `tools/__init__.py` 会自动加载该工具，因此适配器直接加载核验后的必要模块，以模块局部导入映射解析 `src.tools.base`；不修改原始字节，也不创建全局 `sys.modules['src']` 别名。

[`NativeEComTools`](../src/procure_rl/env/upstream.py) 提供：

```python
native = NativeEComTools(db_path, persona=persona, clarification_script=script)
schemas = native.schemas()                  # 原生 OpenAI function schema 列表
observation = native.call(name, arguments)   # 真实原生工具执行，dict 返回
state = native.snapshot()                   # 私有回放状态，不送入模型
native.restore(state)
native.close()
```

参数验证补充拒绝未知字段、缺失必填字段、错误类型和超过 10 个候选；项目 `recommend_product.checks` 是 session 扩展，传原生工具前移除。工具错误不隐式改为成功；例如不存在的推荐 ID 返回 `recommended_product=None`，终局由项目独立验证器判断。

原生连接会请求 WAL，不能满足项目不可变商品访问，因此项目子类仅覆盖 `_get_conn()` 为 `mode=ro&immutable=1` + `PRAGMA query_only=ON`。不修改上游 SQL/FTS/工具行为。只接收已提交、无待处理 WAL/journal 的固定数据库，每个 split 独立文件，不将全量数据库暴露给训练会话。测试确认工具执行后数据库内容哈希不变且没有生成 sidecar。

## 澄清与快照语义

固定[澄清源码](https://raw.githubusercontent.com/Morizeyao/EComAgentBench_/97eff345811fdf652a2135d38d874f2932e11702/src/tools/ask_user.py)接受 `clarification_slots`、`default_response`、`max_clarification_turns`；slot 含 `slot_id`、`trigger_keywords`、`user_response`。每次调用先递增计数；超过 100 字符仍消耗回合。已揭示 slot 不重复匹配，词串/部分词匹配积分最高者被揭示；并列按 slot 顺序。项目保留该确定性行为，不将其视作语义 LLM 澄清。

原生工具快照字段固定为：

```json
{
  "upstream_revision": "97eff345811fdf652a2135d38d874f2932e11702",
  "configuration_sha256": "hash of database path, persona and clarification config",
  "clarification": {
    "turn_count": 0,
    "slots": [{"slot_id": "example", "revealed": false}]
  }
}
```

仅 slot ID/揭示标志进入原生状态，回答保存在配置中。配置和 revision 不一致时拒绝恢复。项目外层快照另外包含任务/数据库内容哈希、剩余步骤、历史、事件、策略版本与 RNG，并用真实动作重放比较；原生快照本身不代表完整训练恢复。

## 兼容 SQLite 最小结构

S1 的自建数据库同时保留项目事实表和上游所需视图/表。九个工具的最小 SQL 为：

```sql
CREATE TABLE products (
    product_id TEXT PRIMARY KEY, title TEXT, store TEXT, brand TEXT, data TEXT
);
CREATE VIRTUAL TABLE products_fts USING fts5(title, content='products');
CREATE TABLE reviews (
    review_id INTEGER PRIMARY KEY, product_id TEXT, rating REAL,
    title TEXT, text TEXT, helpful_vote INTEGER,
    verified_purchase INTEGER, timestamp INTEGER
);
CREATE VIRTUAL TABLE reviews_fts USING fts5(
    title, text, content='reviews', content_rowid='review_id'
);
-- Insert all products/reviews, then rebuild the external-content indexes:
INSERT INTO products_fts(products_fts) VALUES('rebuild');
INSERT INTO reviews_fts(reviews_fts) VALUES('rebuild');
```

`products.data` 是带 `product_id/title/store/price/details/features/...` 的 JSON，价格与 rating 由 JSON 读取。上游生成任务的采样 API 另用多项索引列；S1 不运行这些采样入口。不能把这个工程最小结构冒充完整官方数据库。

## 评分差异与实际验证

固定[官方 judge](https://raw.githubusercontent.com/Morizeyao/EComAgentBench_/97eff345811fdf652a2135d38d874f2932e11702/src/evaluation/judge.py)的 `RubricJudge.judge_sample()` 调用 `LLMClient.chat_json()` 对自然语言 rubric 判定；不是可直接离线调用的确定性验证器。官方汇总判准确的逻辑为 exact target match 或全部 rubrics 满足。项目终局/过程验证器是 S1 新增能力，不能据本次 CPU 工程测试报告官方准确率或 LLM judge 一致性。

在学校 Linux、项目 `.venv-cpu`/Python 3.11.16 执行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p test_upstream.py -v
```

**实际 5/5 通过，0 失败/错误/跳过**：真实标题 FTS、属性过滤、详情、评论 FTS、统计、店铺、画像、推荐；只读连接与文件哈希；同快照动作重放；两会话并发隔离；澄清长度/回合边界；源码篡改与未 checkpoint 数据库拒绝。未使用 mock/stub，无额外 Python 包安装。初次测试导入恰遇并行开发中的 `env/__init__.py` 引用尚未落地 session 而失败，待实际文件落地后执行通过；它不是上游兼容问题。

代码已完成与原生 CPU 工具集成已验证；全阶段验收、日志路径与最终测试总数以 `PROGRESS.md` 为准。完整官方 DB、官方任务端到端、教师 API、LLM judge 与 GPU 均未执行，不属于本次 S1 CPU 工程证据。
