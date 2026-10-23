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
| `review_material.py` | 从已核验数据包生成中文人工审阅材料、完整合法解/原句/同根反事实、空白签核表和未执行的独立模型输入；材料含私有答案，只能交审核者，不能交执行教师/学生 | S2；`scripts/data/prepare_s2_review.py` 调用；导出不代表审核完成 |
| `independent.py` | 从train/dev私有审核材料生成完整task/hash绑定prompt，严格解析全部七项语义检查与accept/reject，任何不确定/失败要求reject；拒绝sealed/official表达、重复key和矛盾决定。不导入模型/网络/GPU | S2；`scripts/data/run_s2_independent_review.py`实际执行器调用，GPU证据与人工签核分别记录 |
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

真实采集 v1 暴露未澄清隐藏需求与相近值误判，当前通用提示为 `procure-teacher-visible-v2`、API策略 `s2-expert-tool-v2`；主动澄清常见采购维度并严格按结构化值判断。提示不接收私有约束或合法解，验证标准不变。旧 v1 提示保留注册，历史轨迹仍能独立回放。整个缓存目录共用请求/费用预留上限，改提示/模型/策略不会重置预算。

**`configs/s2-teacher.json` 是用户授权 Codex 暂选的默认建议，可直接查看修改；尚未以本项目实测确认最优。** 默认 `deepseek-flash`、`thinking: {type: disabled}`，源于2026-10-22官方文档。`expected_model_revision` 记录文档当时映射 `DeepSeek-V4.1-Flash-1017`，它是可变别名说明；真实不可变 `model_revision` 仍为 null，不能用文档版本冒充实际服务端固定 revision。依据、价格和原始 HTML 哈希见 [来源审计](../../../docs/s2-source-audit.md)。

密钥单独放项目 `.secrets/deepseek_api_key`（已忽略），配置只保存 `key_file` 路径；不得把密钥放进配置、命令、日志或聊天。HTTP Authorization 仅在内存构造，日志只留脱敏请求/响应。**已实际执行两批真实教师，共72请求；v2为1/2回放接收、离线缓存重现一致且新请求0**。真实采集命令如下：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/my-s2-build/dataset --execute-api --limit 2 --cache-directory logs/my-s2-teacher-cache --output logs/my-s2-api
```

该命令显式允许教师网络请求及配置内预算，默认最多80请求、pilot预算2 USD、单次保留0.025 USD；估价采用配置的 peak cache-miss 单价，provider账单未知时保持 null。`new_request_cost_estimate_usd` 排除本地缓存命中的重复计费，`cost_usd` 保留原响应usage的等价值。缺密钥写 `not_run_missing_credentials`，不算真实教师测试失败或通过。请求前持久化 pending，超时/网络/计费不确定不自动重发；保留 journal 并核对供应商记录。再次离线复现使用相同配置与缓存：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/my-s2-build/dataset --cache-only --limit 2 --cache-directory logs/my-s2-teacher-cache --output logs/my-s2-cache-replay
```

缓存绑定请求、提示、配置和策略哈希；缺缓存明确拒绝，不自动联网。保留旧数据包和输出，修改来源/模板/教师配置后创建新 build/run，不复用不一致的状态。本阶段没有训练 checkpoint 或优化器恢复。

## 审核与未完成门槛

先导出可读材料再做真实人工审核。默认仅 train/dev；封存任务需显式 `--include-sealed-test`，仅用于数据质量审核，不用于模型/奖励选择。导出会核验数据包库存哈希并保存命令、机器、解释器、数据/代码/输出哈希。输出 `review.md`、`review-material.json`、`reviews-template.json`、`independent-inputs.jsonl` 与运行清单。空白签核表不能通过审计；独立模型输入仍标 `not_run`。

```bash
PYTHONPATH=src .venv-cpu/bin/python scripts/data/prepare_s2_review.py --dataset logs/my-s2-build/dataset --output logs/my-s2-review-material
```

PLAN 的 S2 顺序是先小规模端到端验收，再扩规模。小 pilot 的代码/真实教师回放可以单独报告；至少200条人工抽检及下述门槛继续约束正式数据发布，不因 pilot 不足200而声称已经满足，也不通过重复记录补数。

`--reviews` 是可选 JSON 文件，含 `human_reviews`、`identity_reviews`、`independent_reviews` 三个列表；它应保存实际签核，不能把 pending 队列直接改成通过。人工任务签核需 `task_id/task_sha256/role=human/reviewer/reviewed_at/decision`，家族签核需 `product_id/product_sha256/family/role=human/reviewer/reviewed_at/decision`；哈希必须对应当前数据包。人工reject或冲突保持withheld；模型reject须有实际人工裁决并标记 `adjudicates_model_disagreement`。

独立模型审核必须保存 `task_id/task_sha256/status=completed/decision`、`model`、真实非 unknown 的 `model_revision`、带时区 `reviewed_at`、`prompt_version`、`prompt`、`prompt_sha256`、`raw_response`、`response_sha256`。`prompt` 为含完整 `task` 与对应 `task_sha256` 的结构化对象；两份 SHA 使用 `procure_rl.env.catalog.digest` 的规范 JSON 算法，不能用不同缩进文件的 byte SHA 替代。原始文件路径/byte SHA 可另行保留。`independence_basis={"method":"different_model","generation_models":[实际生成教师模型标识]}` 声明复核模型与生成模型不同，同名模型拒收。缺字段、任务不符、原始输入/输出 SHA 不符或不带时区的记录不计入审核。

发布门槛会用 `independent.parse_independent_response` 重新解析真实 runner 的 `raw_response.generated_text`；也支持含完整标准响应的原始JSON字符串或直接响应对象。解析出的 `decision/checks/reasons` 必须与审核记录完全一致，七项检查和accept/reject关系沿用严格解析规则。无法解释的raw对象、token上限截断、修改决定/检查/理由但保留原始生成文本的记录均拒收；只匹配原响应SHA不足以通过。

这些检查只验证模型身份声明不同及原始内容绑定，不能自动认证外部执行、判断不同别名是否其实同一模型、或保证原始响应判读正确。发布者仍须审计实际模型 revision、调用日志/本地执行记录和原始响应；不能用补字段的方式制造“独立”审核。

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-audit --dataset logs/my-s2-build/dataset --collection logs/my-s2-api --reviews logs/my-s2-human-reviews.json --output logs/my-s2-release-audit
```

audit 输出重新计算的 `replay-ledger.json`、`release-decision.json` 与报告。审计 `status=passed` 仅表示审计过程完成，仍需查看 `ready_for_formal_training` 和 `stage_complete`；`status=withheld` 的发布决定不产生正式可用专家列表。门槛包括官方家族/近重复元数据完整、商品家族人工确认、至少200条有效人工任务审核、所有分歧裁决、独立语义复核及真实教师成功轨迹回放与人工批准，不能用工程脚本或词面语义候选替代。

当前官方索引按整品牌保守排除，另加入3个缺 Brand 目标有 store/Manufacturer/title 佐证的候选别名；`metadata_complete=false`，不冒充人工身份确认。真实来源只是小量历史研究 metadata，未进行正式200条人工抽检。真实API教师已执行，学校独立8B状态与正式全量测试见PROGRESS。S2离线构建/真实SQLite回放无需GPU；8B复核另记录实际获分配UUID、模型revision和执行证据。

常见错误：`ModuleNotFoundError` 检查根目录和 `PYTHONPATH=src`；哈希不符从固定输入创建新数据包，不绕过校验；无任务先看 rejections 和 quarantine，不擅自去掉排除或放宽事实；输出目录存在换新目录；API失败检查脱敏journal和预算，不自动重复潜在付费请求。CPU全量结果以 PROGRESS 的正式测试日志为准，loopback HTTP协议测试需要执行上下文允许本地临时socket，不访问外部教师。
