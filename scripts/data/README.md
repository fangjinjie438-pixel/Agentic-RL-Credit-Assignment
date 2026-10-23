# S2 数据来源工具

| 文件 | 用途、输入输出与阶段 |
| --- | --- |
| `fetch_amazon_pilot.py` | S2固定来源有界HTTP Range抽取；输入固定公开URL/新输出，输出原始metadata与下载哈希，不生成任务或教师轨迹 |
| `audit_source_coverage.py` | S2来源覆盖诊断；输入已核验1000行/source manifest/保守官方排除索引，输出逐字段与办公类别统计、严格来源候选摘录和整簇quarantine证据；不改fixture/config/dataset，不创建任务或审核通过 |
| `prepare_s2_review.py` | S2离线审阅导出；输入已构建数据包/新输出，验证库存后导出中文`review.md`、任务/原句/完整合法解、未签核JSON表与未执行独立模型输入，以及RunRecord。默认仅train/dev，封存需显式选择；不访问教师/GPU，不创建审核决定 |
| `fetch_qwen3_review_model.py` | S2独立8B模型获取；输入官方精确commit/新证据目录，CPU标准库下载到项目models并核验全部LFS SHA256/普通文件Git blob SHA1；支持新证据目录续传`.part`，不加载模型 |
| `run_s2_independent_review.py` | S2真实独立模型审核；输入核验数据包/本地固定模型/模型完整性报告/明确分配文件及UUID，单卡BF16/SDPA关闭thinking，最多7条train/dev、16K上下文/1024生成token；输出完整prompt、原始token/文本、严格JSON决定及机器/依赖/GPU/哈希证据；不产生人工通过或训练 |

`fetch_amazon_pilot.py` 只在人工选择来源时用 HTTP Range 从固定 HF revision 的 Electronics Parquet 首个 row group 抽取元数据。输入固定公开 URL、新输出目录；输出网络请求/字节/哈希清单与原始 JSON 元数据，不生成训练任务，不加载模型或访问教师 API。运行时隐藏 GPU，仅导入项目已装 PyArrow 和标准库。

```bash
CUDA_VISIBLE_DEVICES='' .venv-cpu/bin/python scripts/with_proxy.py -- .venv-gpu/bin/python scripts/data/fetch_amazon_pilot.py --output logs/my-s2-source
```

实际验证状态与来源边界见 `docs/s2-source-audit.md`。输出目录须不存在；失败保留现有证据、换新目录恢复。固定版本下载失败时不自动更换数据源或 revision；无需 GPU、系统 Toolkit 或 checkpoint。普通离线 S2 流水线不依赖 PyArrow。

诊断已有来源可扩充的下界，CPU开发与学校Linux使用同一命令：

```bash
PYTHONPATH=src .venv-cpu/bin/python scripts/data/audit_source_coverage.py --output logs/my-s2-source-coverage
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_source_coverage.py' -v
```

脚本先核验 `rows.json` byte SHA 和固定 HF revision，按明确办公设备叶类别筛选，标题只排除明显配件/非完整设备；不从标题提取规格。候选必须同时具有实际 `price`、结构化 `details.Brand`、带受支持质量单位的 `Item Weight`、有限颜色词表中的完整 `Color`（或这些颜色的明确组合）。缺字段、含糊单位、非颜色描述、拼写疑似错误保留拒收原因，不纠正或补猜；`Manufacturer/store` 不代替 Brand。使用 S2 normalizer 再核验每条 fact/原句/UTF-8 raw digest，调用现有家族/近标题整簇官方隔离逻辑作诊断。

输出 `report.json`、1000行 `row-audit.json`、`quarantine-audit.json`、`normalization-rejected.json`、`candidate-records.json` 与 `quarantined-records.json`；两份摘录均保留原始row/raw/hash/source/facts，标记 `diagnostic_only_unreviewed_not_formal_dataset`，人工审核数和新任务数仍0。来源初始1000行不具总体代表性，保守规则给出候选下界，不能推算完整数据集容量或声称长程任务所需接口/兼容性证据已足够。官方索引 `metadata_complete=false` 仍原样报告。恢复时换新输出目录，不覆盖源文件或旧数据包；哈希不符须回查固定来源，不绕过检查。

**实际已验证：** `logs/s2-source-coverage-20261022-v3/` 中，1000行有74条办公设备范围候选，19条同时具备严格price/Brand/weight/color并通过原字段归一化；官方整簇隔离7条，保留12条、11个品牌家族。74条中price缺45、颜色缺28/非保守词表9，未补猜。新8项CPU测试全过，原始日志为 `logs/s2-source-coverage-20261022-tests-v2/`。早期v1误用task digest导致4条Unicode raw hash被拒，后已改为来源UTF-8规范hash并加入回归；v2保留更窄颜色词表的历史结果，最终v3明确支持常见颜色名及这些颜色的组合。所有摘录仍未人工审核，未改当前fixture/config/dataset。

从已核验数据包准备实际人工审阅：

```bash
PYTHONPATH=src .venv-cpu/bin/python scripts/data/prepare_s2_review.py --dataset logs/my-s2-build/dataset --output logs/my-s2-review-material
```

材料包含私有约束和答案，仅给审核者。逐条完成实际核验后，将`reviews-template.json`复制为新文件并填写真实身份/时间/accept或reject/说明，再交给`s2-audit --reviews`。原模板保持空白。导出成功只说明材料生成，不表示人工/模型审核或正式发布通过。哈希不符时重新从固定输入构建新数据包，不跳过库存检查；输出目录重复时换新目录恢复。本脚本与普通S2使用项目CPU环境标准库；不依赖来源抽取用的PyArrow。

**实际已验证：** `logs/s2-20261022-api/review-material-v2/` 从新官方保守别名索引构建的数据 revision `s2-f692f21320912220be59d4a5` 导出7条任务与8条商品。人工200抽检仍差193，签核表保持空白，模型输入标为not_run；来源/命令/解释器/输出SHA见该目录run.json。独立审核记录的严格字段与SHA算法见[data README](../../src/procure_rl/data/README.md)。

`audit_official_identities.py` 使用标准库和项目 `RunRecord`，校验固定 ECom benchmark SHA 后，只投影缺 Brand 官方目标的 product ID、title、store、Manufacturer 和明确型号。它对 store/Manufacturer 一致或 title 同 store 前缀的情况，增加保守整品牌别名以供 quarantine；输出 `identity-audit.json`、新的 `official-exclusions-candidate.json` 和运行清单。**候选不是原始 Brand 补录，也不是人工通过；`metadata_complete=false` 和原缺 Brand ID 均保留。** 不读取官方 query/persona/rubric作训练输入，不改变现有 fixture，不访问网络、模型、教师或 GPU。

```bash
PYTHONPATH=src .venv-cpu/bin/python scripts/data/audit_official_identities.py --output logs/my-s2-official-identity-audit
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_official_identity_audit.py' -v
```

CPU 开发与学校 Linux 使用同一命令，预期生成 3 个目标的候选证据及 3 个新增整品牌别名；实际状态见对应 run.json。只有审阅候选并修改构建配置到新排除索引后，重建新 dataset revision 才会使用它；不要覆盖已哈希数据包。来源 SHA 不符即失败，保留失败输出并回查固定 source/index，不自动更换 revision。

**实际已验证：** `logs/s2-official-identity-audit-20261022-v1/` 已完成固定 SHA 的元数据候选审计，3 个缺 Brand 目标均找到候选别名；其 `tests/` 记录新增 5 项 CPU 测试全过。正式 metadata/人工门槛仍未通过，不据此放行训练数据。后续代码版本的复验见同根 `v2` 日志，原证据不覆盖。

独立语义模型采用[官方Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B)，固定commit `b968826d9c46dd6066d109eabc6255188de91218`。官方模型卡说明Transformers>=4.51.0与`enable_thinking=False`；既定4.53.2保持不升级。8B只做数据审核，不改变4B主实验或升模协议。下载与GPU实际验证状态以运行清单为准；以下命令准备完毕，未执行部分不能写通过。

```bash
PYTHONPATH=src CUDA_VISIBLE_DEVICES='' .venv-cpu/bin/python scripts/with_proxy.py -- .venv-cpu/bin/python scripts/data/fetch_qwen3_review_model.py --revision b968826d9c46dd6066d109eabc6255188de91218 --output logs/my-s2-8b-download
PYTHONPATH=src CUDA_VISIBLE_DEVICES='' .venv-gpu/bin/python scripts/data/run_s2_independent_review.py --dataset logs/my-s2-build/dataset --model models/Qwen3-8B/b968826d9c46dd6066d109eabc6255188de91218 --model-report logs/my-s2-8b-download/model-verified.json --allocation logs/s2-20261022-api/allocation-user-confirmed.json --gpu-uuid GPU-2e81c395-ac38-bfde-adba-34f3d967f7af --output logs/my-s2-8b-preflight --prepare-only
PYTHONPATH=src .venv-gpu/bin/python scripts/data/run_s2_independent_review.py --dataset logs/my-s2-build/dataset --model models/Qwen3-8B/b968826d9c46dd6066d109eabc6255188de91218 --model-report logs/my-s2-8b-download/model-verified.json --allocation logs/s2-20261022-api/allocation-user-confirmed.json --gpu-uuid GPU-2e81c395-ac38-bfde-adba-34f3d967f7af --output logs/my-s2-8b-review --execute
```

CPU开发可验证`test_data_independent.py`的严格解析和split隔离；实际学校GPU执行需仍有效的授权文件/UUID，脚本先只读核验后将可见性限定该卡，再核验CUDA runtime UUID。无分配时不运行`--execute`。模型下载中断换新output续传，同一commit逐SHA通过才接收；哈希失败保留`.part`和失败证据，回查来源，不跳过校验。响应非JSON、重复key、缺检查、理由为空、决定与检查矛盾或截断均拒收为失败，不自动“修复”响应。`reviews.json`可以传给`s2-audit --reviews`，模型reject会进入人工裁决门槛；不得把模型accept当人工签核。

本机下载诊断表明官方代理长连接较慢；镜像直连16MiB实测3.64秒（包含redirect），已选择同一commit的镜像字节传输作为恢复方案。`--transport-base-url https://hf-mirror.com --direct-transport --workers 3`加在下载命令后，仅改变权重传输路径：metadata仍从官方HF获取，输出同时记录官方URL/实际镜像URL，全部权重须与官方LFS SHA256一致。最多3连接，不重复完整下载已保留partial。原官方v1中断证据与镜像v2保留在`logs/s2-20261022-api/independent-model-download-v{1,2}/`；下载及推理是否全部完成请查看对应run.json，不能从速度probe推断完成。GPU执行会在分配卡可用显存少于30,000MiB时停止；该容量检查不构成资源分配依据。

**实际已验证（2026-10-22）：**下载v2的13文件全部通过官方内容标识核验，5个权重合计16,381,516,776 bytes；报告为`logs/s2-20261022-api/independent-model-download-v2/model-verified.json`。初次GPU自动审批因仅有历史授权日志而拒绝，完整原因保留在`independent-review-blocked-v1/`，当时未创建CUDA上下文。随后用户直接确认“确认，本次可使用该 GPU 5”，新授权文件明确仅本次7任务单卡推理；未来执行须使用届时仍有效的分配，不能从本例永久认领该卡。

CPU首轮预检发现原prompt为16,791–17,431输入token，超过16K。已保留失败，不截断任务或事实；仅将相关任务摘要的重复evidence-ID清单和重复provenance哈希改为完整输入SHA绑定，保留完整当前task、所有商品事实/原句/原单位/规范单位、manifest SHA。`independent-cpu-context-v2/report.json`实测7,489–7,822输入token，预留1024输出全部满足16K；CUDA未初始化。现有4项CPU测试已覆盖任务完整性及事实/原句/单位投影不变。

`logs/s2-20261022-api/independent-review-v1/`已实际在GPU5运行，runtime UUID与分配一致；Torch2.7.1+cu126、Transformers4.53.2、BF16/SDPA、关闭thinking、并发1/CPU线程2、seed0。7/7原始响应严格解析并通过完整prompt/响应SHA追溯，模型accept=0/reject=7、格式失败0；总输入53,647/输出2,794 token，生成累计253.17秒，峰值allocated18,382,922,240/reserved19,744,686,080 bytes。仅审核train，未读sealed/official任务表达、未训练或产生checkpoint。`independent-review-cleanup-v1.json`确认精确本进程已退出、GPU compute apps不含该PID，未调整他人进程。

7个reject均为待人工裁决的模型意见。其理由包含对规范化g与原始lb/oz并存、未约束的connectivity/OS字段及无反事实兄弟base的疑似误判；不能据此直接将程序已验的单位换算/可行解/两对CF改判错误，也不能当作人工拒收。完整`reviews.json`可用于发布审计；真实人工审核、商品身份与官方元数据门槛仍保留，S2未据本次模型推理自动放行。
