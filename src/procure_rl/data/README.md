# S2 数据流水线

本目录实现事实归一化→家族/型号/近重复聚类→先 split 后任务表达→可行性与反事实→工具采集→真实回放→发布审核。离线入口仅使用项目 `.venv-cpu`、标准库与 S1 的真实 SQLite/原生工具；不加载模型或初始化 GPU。教师调用由 `s2-collect --execute-api` 明确选择。阶段范围、验收与交接见 [S2](../../../docs/stages/S2.md) 和 [PROGRESS](../../../PROGRESS.md)。

| 文件 | 用途、输入输出与调用关系 | 阶段及执行入口 |
| --- | --- | --- |
| `__init__.py` | 包说明；导入不执行网络、模型或 GPU 操作 | S2；由项目 CLI 导入 |
| `sources.py` | `normalize_records` 输入原始 metadata、原记录哈希、明确原字段/原句/单位及版本来源，使用 Decimal 校验美元价格与 g/kg/lb/oz/W 转换；输出无 split 的 S1 product/evidence、拒收原因和来源清单。缺失/冲突事实拒收，不从标题猜规格 | S2；`pipeline.build_dataset` 调用 |
| `split.py` | 商品按 family、品牌型号、规范文本哈希、MinHash 候选后精确 Jaccard 聚类；对提供的官方 ID/家族/型号/标题命中整簇 quarantine，再按种子划分 train/dev/sealed_test。输出商品、映射、排除记录和覆盖审计；语义候选使用受控同义词 token cosine，供后续审核，不能替代独立 8B | S2；build 前调用；`audit_task_splits` 检查兄弟任务和商品引用边界 |
| `builder.py` | 输入已划分商品与约束模板，先对整个检索 split 求全部合法解，再生成英文 query/persona/clarification；按单一约束改动构建反事实并重算解集。输出任务、拒收与字面泄漏审计；`apply_expression_rewrite` 只改表达，保留事实和兄弟 split | S2；build 调用，无教师依赖 |
| `teacher.py` | `collect_episode` 只把初始 observation、工具 schema 与已见工具结果送给策略，实际执行 S1 工具并保存公开对话/结构化轨迹。`ScriptedTeacher` 是工程策略；`OpenAIHTTPTeacher` 支持受预算限制的 HTTP 与持久请求缓存，保留原响应/usage/估算成本和失败，无自动重发不确定请求 | S2；collect 入口选择 engineering/API/cache-only；脚本轨迹不作为专家训练示范 |
| `replay.py` | `replay_episode` 输入独立 split Catalog、私有任务及采集轨迹，重新实际执行每个动作，比较身份、公开对话、observation、事件、奖励、终局与状态哈希；输出接收/拒收 ledger。真实 HTTP 专家资格还需请求/响应证据一致；不信任轨迹中自报成功 | S2；collect 逐条调用，audit 再次调用；离线不访问教师 |
| `review.py` | 从任务/商品/词面语义候选生成待人工/家族/独立模型审核队列；`release_gate` 输入真实回放 ledger 和绑定内容哈希的审核记录，输出 ready/withheld 原因，不填造人工或模型签核 | S2；build/collect/audit 调用 |
| `pipeline.py` | `build_dataset` 将原始摘录按source_row_index绑定到核验SHA的rows.json，写可追溯数据包及manifest；`load_dataset` 核验产物哈希，采集只加载 train/dev、仅遍历 train；`collect_dataset` 分开工程与专家产物；`audit_release` 校验集合身份并重新回放后评估审核与正式发布门槛 | S2；CLI `s2-build`、`s2-collect`、`s2-audit` |

## CPU 开发与学校 Linux 命令

以下从项目根目录运行，输出必须是新目录。真实来源的离线构建已实际执行，`build-real-v1` 是历史小规模成功证据；扩充官方目标 metadata 后的最终命令和结果以 PROGRESS 为准，不据旧 run 宣称完整 S2 验收。

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-build --config configs/s2.json --output logs/my-s2-build
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/my-s2-build/dataset --engineering --limit 2 --output logs/my-s2-engineering
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-audit --dataset logs/my-s2-build/dataset --collection logs/my-s2-engineering --output logs/my-s2-audit
PYTHONPATH=src .venv-cpu/bin/python scripts/run_cpu_tests.py --stage S2 --config configs/s2.json --output logs/my-s2-tests
```

工程配置 `configs/s2-engineering.json` 可替代上面 build/collect 的 `configs/s2.json`，其输入是 S1 虚构夹具；此来源永久标记 engineering-only。真实配置为 `configs/s2.json`，输入 `fixtures/s2/amazon-electronics.json` 的12条真实商品，先经过官方排除再构建任务，缺字段或无合格反事实的候选留在拒收清单，不扩充凑数。正式数量目标仍按 PLAN，当前小包不是规模目标已达成。

build 预期输出 `report.json`、`run.json/run.log`、`dataset/manifest.json`、`catalog.json` 及物理隔离只读 SQLite、`tasks/{train,dev,sealed_test}.json`、来源/split/task审计、quarantine、rejections、review-queue 和 release-gate。数据包 manifest 记录每个产物 SHA，采集前重新校验；封存测试需显式加载权限，默认采集不遍历。collect 输出逐任务 `episodes/.../episode.json`、`accept-reject-ledger.json`、`release-gate.json`、`expert-candidates.jsonl` 及报告。工程模式允许真实环境回放接收，但 `expert-candidates.jsonl` 保持空；API成功候选也须通过发布审核才能用于正式训练。

## 暂定教师与真实采集

**`configs/s2-teacher.json` 是用户授权 Codex 暂选的默认建议，可直接查看修改；尚未以本项目实测确认最优。** 默认 `deepseek-flash`、`thinking: {type: disabled}`，源于2026-10-22官方文档。`expected_model_revision` 记录文档当时映射 `DeepSeek-V4.1-Flash-1017`，它是可变别名说明；真实不可变 `model_revision` 仍为 null，不能用文档版本冒充实际服务端固定 revision。依据、价格和原始 HTML 哈希见 [来源审计](../../../docs/s2-source-audit.md)。

密钥单独放项目 `.secrets/deepseek_api_key`（已忽略），配置只保存 `key_file` 路径；不得把密钥放进配置、命令、日志或聊天。HTTP Authorization 仅在内存构造，日志只留脱敏请求/响应。真实采集命令如下，**本轮尚未运行真实教师**：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/my-s2-build/dataset --execute-api --limit 2 --cache-directory logs/my-s2-teacher-cache --output logs/my-s2-api
```

该命令显式允许教师网络请求及配置内预算，默认最多80请求、pilot预算2 USD、单次保留0.025 USD；估价采用配置的 peak cache-miss 单价，provider账单未知时保持 null。`new_request_cost_estimate_usd` 排除本地缓存命中的重复计费，`cost_usd` 保留原响应usage的等价值。缺密钥写 `not_run_missing_credentials`，不算真实教师测试失败或通过。请求前持久化 pending，超时/网络/计费不确定不自动重发；保留 journal 并核对供应商记录。再次离线复现使用相同配置与缓存：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/my-s2-build/dataset --cache-only --limit 2 --cache-directory logs/my-s2-teacher-cache --output logs/my-s2-cache-replay
```

缓存绑定请求、提示、配置和策略哈希；缺缓存明确拒绝，不自动联网。保留旧数据包和输出，修改来源/模板/教师配置后创建新 build/run，不复用不一致的状态。本阶段没有训练 checkpoint 或优化器恢复。

## 审核与未完成门槛

`--reviews` 是可选 JSON 文件，含 `human_reviews`、`identity_reviews`、`independent_reviews` 三个列表；它应保存实际签核，不能把 pending 队列直接改成通过。人工任务签核需 `task_id/task_sha256/role=human/reviewer/reviewed_at/decision`，家族签核需 `product_id/product_sha256/family/role=human/reviewer/reviewed_at/decision`；哈希必须对应当前数据包。独立模型审核需绑定任务哈希、`status=completed`、`decision` 和真实 `model_revision`，保留独立模型身份与原始结果。人工reject或冲突保持withheld；模型reject须有实际人工裁决并标记 `adjudicates_model_disagreement`。

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-audit --dataset logs/my-s2-build/dataset --collection logs/my-s2-api --reviews logs/my-s2-human-reviews.json --output logs/my-s2-release-audit
```

audit 输出重新计算的 `replay-ledger.json`、`release-decision.json` 与报告。审计 `status=passed` 仅表示审计过程完成，仍需查看 `ready_for_formal_training` 和 `stage_complete`；`status=withheld` 的发布决定不产生正式可用专家列表。门槛包括官方家族/近重复元数据完整、商品家族人工确认、至少200条有效人工任务审核、所有分歧裁决、独立语义复核及真实教师成功轨迹回放与人工批准，不能用工程脚本或词面语义候选替代。

当前官方索引已覆盖可得的目标 ID/品牌/明确型号/标题，并按整品牌保守排除；3个目标缺品牌，`metadata_complete=false`。真实来源只是小量历史研究 metadata，未进行正式200条人工抽检；学校独立8B语义复核与真实API教师采集尚未执行，均独立保留未完成状态。S2离线构建/真实SQLite回放无需GPU；未来8B复核必须另记录实际获分配UUID、模型revision和执行证据。

常见错误：`ModuleNotFoundError` 检查根目录和 `PYTHONPATH=src`；哈希不符从固定输入创建新数据包，不绕过校验；无任务先看 rejections 和 quarantine，不擅自去掉排除或放宽事实；输出目录存在换新目录；API失败检查脱敏journal和预算，不自动重复潜在付费请求。CPU全量结果以 PROGRESS 的正式测试日志为准，loopback HTTP协议测试需要执行上下文允许本地临时socket，不访问外部教师。
