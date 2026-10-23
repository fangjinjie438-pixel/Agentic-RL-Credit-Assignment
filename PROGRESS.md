# Procure-RL 进度与交接

最近更新：2026-10-22T05:12:10+08:00（Asia/Shanghai）。执行机器：学校Linux `A6000`。当前阶段：**S2 不依赖人工的本轮实施与验证已完成，按用户要求暂停等待人工审核**。真实教师/API缓存、独立8B真实GPU推理、CPU测试与发布审计均已执行；正式数据仍withheld，整阶段未放行。人工抽检、商品/官方身份确认与7条模型分歧由用户稍后裁决；下一步仍是S2，不自动进入S3。

## 初始基线（实施开始时的事实）

**计划已确定，代码尚未实现，服务器环境尚未验证。** 当时没有checkpoint、训练结果或已锁定GPU环境。下面记录随后实际完成的工作，不回填初始状态。

## 阶段状态

| 阶段 | 代码状态 | CPU/只读验证状态 | 学校真实GPU验证状态 |
| --- | --- | --- | --- |
| S0 工程与运行环境 | 配置、运行清单、doctor、隔离导入、授权GPU预检、代理与独立工具链完成 | 39项CPU测试、25项隐藏GPU依赖检查通过；实际硬件盘点完成 | 双卡BF16/P2P/NCCL、FlashAttention前反向、0.6B单提示推理通过；训练兼容待后续阶段 |
| S1 环境与验证器 | 固定 ECom 适配、只读商品库、协议/会话/快照、终局/过程验证器完成 | 新增43项S1测试，合计82项全过；27项真实CPU端到端验收全过 | 不适用：S1固定小样本验收不需要GPU；本轮未运行 |
| S2 数据流水线 | 构建/家族隔离/去重/反事实、受限HTTP、真实回放、独立审核与人工材料代码已实现 | 最终160项全量通过（含上下文修复）；真实教师v2=1/2接收，缓存重现一致且新增请求0 | 独立Qwen3-8B在本次确认GPU5真实完成7/7推理，7条模型reject待人工裁决；本进程已退出，非训练/LoRA验收 |
| S3 SFT与真实多轮推理 | 未实现 | 未执行 | 未执行 |
| S4 终局RL baseline | 未实现 | 未执行 | 未执行 |
| S5 动作级信用分配 | 未实现 | 未执行 | 未执行 |
| S6 纠错闭环 | 未实现 | 未执行 | 未执行 |
| S7 正式评测与交付 | 未实现 | 未执行 | 未执行 |
| S8 可选OPD | 未实现，独立扩展 | 未执行 | 未执行 |

## S2 接续：用户配置密钥后的真实执行

用户明确表示API key已配置，继续完成S2；沿用用户授权的暂定DeepSeek配置，未要求重复确认。按AGENTS→PLAN→PROGRESS→S2顺序读取并检查目录README；不进入S3。

### 已实际完成

- 密钥只核对存在/非空，在内存用于Bearer；不打印或哈希秘密内容。首次自动审批拒绝外发请求，随后核实1000行公开Amazon源的原始SHA与12条摘录绑定、全部任务按固定模板可精确重建，产出 `outbound-provenance-audit.json`，证明仅公开商品与合成采购需求、不含真实用户/组织数据或私有解。相同请求经证据复审批准后执行，未绕过拒绝。
- 首批 `teacher-pilot-v1`：18次真实请求，0/2接收。教师未主动澄清隐藏重量，一条还把Pink与Baby Pink当等值，全部保留失败原始响应。
- 通用提示升级 `procure-teacher-visible-v2`、策略 `s2-expert-tool-v2`：要求主动澄清采购维度并按结构化值精确比较，不注入私有约束/合法解，不放宽验证器。提示注册表保留v1以回放历史。缓存目录跨策略/模型/提示共享80请求/2 USD预留上限，防止改版本重置预算；loopback资格根据绑定endpoint重算，不能翻engineering标志变专家。
- 第二批 `teacher-pilot-v2`：54次请求，15/39步，**1接收、1拒收**；接收者满足全部硬约束、发现需求并引用完整证据，成为1条尚待人工批准的专家候选。失败者反复窄检索未找到合法候选，最终仍推荐已知超重/颜色不符商品；不把它计入专家。
- `teacher-cache-v2`：两条动作、公开对话、最终状态与第二批逐项一致，仍1接收1拒收，**新请求0、新估算费用0**。采集命令因存在质量拒收返回1，非网络/凭据失败。两批共72个新请求均completed，按配置峰值未命中价估算 **0.0754485 USD**，provider实际账单未知/null。模型响应为deepseek-flash，immutable revision未知/null；system_fingerprint仅作另存观测值。72次动作格式合法，不能据两条训练pilot推断一般成功率。
- 三个官方缺Brand目标仅用target_product身份字段审计：store/Manufacturer/title提供候选佐证，新增Alphaline、EtherealKiller、Reolink Digital三个整品牌排除别名。新 `fixtures/s2/official-exclusions-candidate.json` 由当前s2.json采用，原索引/unknown IDs保持；metadata_complete仍false，不伪造Brand或人工确认。
- 新数据revision **s2-f692f21320912220be59d4a5**：12源记录、4quarantine、8保留，产品train/dev/sealed=7/1/0；任务7/0/0、2对反事实，缺字段不补造。旧数据包保持不可变。
- 审阅包 `review-material-v2/review.md`、私有事实/全解集JSON、空白签核表和模型输入已生成：7任务、8商品，实际人工完成0；就样本供给而言，至少200抽检还差193，不能复制补数。已向用户请求真实签核文件路径；尚未收到时继续独立工作。
- 独立review gate加强为模型身份/实际revision/时区时间、完整prompt.task与SHA、raw response与SHA、声明不同模型；从真实generated_text严格重解析并核对decision/checks/reasons，矛盾/截断/不明输出拒收。哈希与声明无法自行认证实际执行或模型别名独立，真实执行来源仍要核查。

### 命令、机器、日志

以下均在学校Linux A6000，Python3.11.16项目独立 `.venv-cpu` 执行；CLI前缀 `PYTHONPATH=src .venv-cpu/bin/python -m procure_rl`。外部教师另用 `.venv-cpu/bin/python scripts/with_proxy.py --` 包装子命令，只有公开/合成的观测与schema发送至 `https://api.deepseek.com/chat/completions`。新日志根 **logs/s2-20261022-api/**。

| 实际动作 | 结果与时间（+08:00） | 日志相对新根 |
| --- | --- | --- |
| `s2-build --config configs/s2.json --output logs/s2-20261022-api/build-identity-v2` | 通过；04:41:47–04:41:53，新revision | build-identity-v2/report.json、dataset/、run.json |
| `s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/s2-20261022/build-real-final/dataset --output logs/s2-20261022-api/teacher-pilot-v1 --cache-directory .cache/s2-teacher --execute-api --limit 2` | 实际API完成，0/2接收，退出1；04:39:26–04:39:44 | teacher-pilot-v1/report.json、episodes、ledger、run.json |
| 同上，dataset改build-identity-v2/dataset、output改teacher-pilot-v2 | 实际API完成，1/2接收，退出1；04:42:08–04:43:08 | teacher-pilot-v2/；expert-candidates.jsonl仅1条候选 |
| 同第二批，`--cache-only`替换`--execute-api`，output改teacher-cache-v2 | 无联网重现，1接收1拒收，退出1；04:43:57–04:43:58 | teacher-cache-v2/ |
| `PYTHONPATH=src .venv-cpu/bin/python logs/s2-20261022-api/evaluate-pilot.py` | 留存产物统计/缓存内容核对通过 | pilot-analysis-v2/summary.json；早期统计kind名称修正前源码留pilot-analysis/executed-source.py，实际无invalid事件，数量结论相同 |
| `PYTHONPATH=src .venv-cpu/bin/python scripts/run_cpu_tests.py --stage S2 --config configs/s2.json --output logs/s2-20261022-api/tests-final` | **151项全过**，0失败/错误/跳过；04:50:36–04:51:02。之后发现raw决定核对漏洞有针对补验 | tests-final/result.json、unittest.log、run.json |
| `PYTHONPATH=src .venv-cpu/bin/python scripts/data/prepare_s2_review.py --dataset logs/s2-20261022-api/build-identity-v2/dataset --output logs/s2-20261022-api/review-material-v2` | 7条任务/8商品材料导出通过；无人工/模型签核 | review-material-v2/run.json、review.md、reviews-template.json |

官方身份审计实际命令 `PYTHONPATH=src .venv-cpu/bin/python scripts/data/audit_official_identities.py --output logs/s2-official-identity-audit-20261022-v2`；逐条证据和SHA见该目录run.json/identity-audit.json，新增5项CPU测试通过。独立Qwen3-8B模型固定官方commit `b968826d9c46dd6066d109eabc6255188de91218`，5个权重共16,381,516,776 bytes；下载已完成，镜像只作传输加速，身份与验收SHA以官方metadata为准。继承本会话GPU5授权UUID `GPU-2e81c395-ac38-bfde-adba-34f3d967f7af`，实际推理前再只读核验容量/UUID；下载不初始化CUDA。

### 接续追加：来源下界、上下文与当前设备确认

来源覆盖诊断实际 `scripts/data/audit_source_coverage.py --output logs/s2-source-coverage-20261022-v3`（项目CPU解释器）：1000行→74办公设备范围→19严格price/Brand/weight/color齐全并归一化通过→官方quarantine7→12商品/11品牌家族，其中4条已在原fixture、8条新增未人工审核候选。74条中价格缺45、颜色缺28/模糊9，未猜测补充；不是总体容量推断，也不提供接口/兼容性长程证据。候选raw/原行/source/hash/facts保留且diagnostic_only，未生成任务、未改当前数据包。新增8项测试全过，早期Unicode raw digest与合成标题重复的开发失败均留存并修正。

独立8B官方固定commit已完成13文件内容核验，5权重16,381,516,776 bytes；下载v1官方代理慢，04:51:43仅中断本任务PID保留partial，v2镜像直连最多3连接续传，04:51:55–04:57:02完成，metadata/内容标识仍来自官方。首次GPU执行自动审批要求本次用户直接确认，未创建CUDA，拒绝原文保留 `independent-review-blocked-v1/`；用户随后明确“确认，本次可使用该GPU5”，本次授权保存 `allocation-user-confirmed.json`，仅GPU5 UUID、7任务推理不训练，未换卡绕过。

CPU tokenizer预检v1真实发现输入16,791–17,431 token，超过16K预算；未加载权重或初始化CUDA。修复只移除比较摘要重复evidence-ID和重复provenance哈希，保留完整当前task、全部商品facts/quotes/raw与规范units/source_field，并绑定完整输入及dataset manifest SHA。v2实际输入7,489–7,822 tokens，加1024输出均<16K，无截断。既有4项针对测试扩展通过；最终完整 **160项、0失败/错误/跳过** 为 `tests-final-v3/`，由实际上下文问题修复触发复验，源码哈希对应最终纯CPU模块。独立GPU进程见 `independent-review-v1/`，启动后先重新核验权重，再核验runtime UUID/实际推理；不以进程启动当推理通过。

用户最新明确：真实人工审核稍后进行，先完成其它不依赖人工的工作后暂停。人工完成数保持0，不要求用户现在签核，不自动S3。

### 最终独立推理、发布审计与暂停

用户新确认后，仅物理GPU5、UUID `GPU-2e81c395-ac38-bfde-adba-34f3d967f7af` 执行。`independent-review-v1/run.json`：05:02:57–05:08:51+08:00，**7/7实际模型审核完成、0accept/7reject、failures=[]，进程退出0**。模型Qwen3-8B官方固定commit b968826d9c46dd6066d109eabc6255188de91218，13文件全部内容核验；实际Torch2.7.1+cu126、Transformers4.53.2、Accelerate1.8.1、safetensors0.8.0，实际驱动560.35.03只读查询、Torch CUDA runtime12.6与NCCL2.26.2分别记录；未执行系统Toolkit/nvcc。BF16/SDPA、thinking关闭、并发1、CPU线程2、16K上下文/最多1024输出，输入共53,647/输出2,794 token；生成累计253.17秒。整个进程354秒含CPU逐权重SHA预检，不将它冒充纯GPU计算时间。峰值allocated18,382,922,240 bytes、reserved19,744,686,080 bytes；没有训练或checkpoint。

7条模型决定均可严格重解析且与raw prompt/response哈希及decision/checks/reasons一致；`independent-evidence-audit-v1.json` all_traceable=true。**模型执行完成不等于模型意见正确或数据审核通过。** 一些模型理由把已归一化g与保留原lb/oz称不一致、把额外商品属性称query泄漏、要求无CF的base必须有CF，均可能是模型误判，不能据此改程序真值；浅层模板/不自然精确阈值等质量意见也留给真实人工核验。全部7条进入强制裁决列表，不重采样以筛出同意，不代替人审。

`independent-review-cleanup-v1.json` 核验精确本次PID3696476已退出且不在GPU compute apps；只查询GPU5，不结束他人进程。`runtime-process.json`、授权原文/文件SHA、CUDA runtime UUID和冻结runner源副本均保留，未使用其他设备。

最终真实回放审计已执行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-audit --dataset logs/s2-20261022-api/build-identity-v2/dataset --collection logs/s2-20261022-api/teacher-pilot-v2 --reviews logs/s2-20261022-api/independent-review-v1/reviews.json --output logs/s2-20261022-api/release-audit-final
```

审计退出0，实际重放两条教师轨迹仍1接收1拒收；独立记录7有效/0无效，1条未人工批准专家候选，人工0、未裁决7，approved_expert_task_ids=[]，stage_complete=false。正式withheld的剩余原因仅为官方家族/近重复覆盖、商品身份、至少200人工抽检、模型分歧裁决、专家人工批准。不能把CPU审计status=passed理解为正式放行。

最后完整CPU命令 `PYTHONPATH=src .venv-cpu/bin/python scripts/run_cpu_tests.py --stage S2 --config configs/s2.json --output logs/s2-20261022-api/tests-final-v3`：**160项、0失败/错误/跳过**；涵盖最终上下文投影修复。早期151/160结果和每次实际问题修复的针对测试均保留，没有覆盖历史。`handoff-final/audit.json` 已实际完成 **220/220一致性检查**：最终source/tests/fixtures/config与真实产物、预算/缓存、模块文档和credential未落入日志，`handoff-final/human-next.md` 汇总模型分歧与后续真实签核动作。

**按用户最新要求在此暂停。** 其它本轮不依赖人工的工作完成，S2不标整阶段完成、不进入S3。用户稍后先读 `review-material-v2/review.md` 与 `handoff-final/human-next.md`；在原模板副本填写真实身份/时间/accept或reject/理由，真实裁决后才填adjudicates_model_disagreement=true。后续将人工human_reviews/identity_reviews与independent-review-v1/reviews.json中的independent_reviews合并另存新文件，确保revision一致，然后用上述s2-audit命令替换--reviews与新--output。被人工拒收任务需先从源/模板修复并重建新revision；不要原地改已哈希数据包。当前7条不足200抽检目标，后续扩充须真实来源和相同防污染/质量门槛，不以复制补数。

### 文件与后续

新增官方身份审计/模型下载/独立模型执行/审阅导出脚本、data independent/review_material模块与对应测试、保守候选索引；修改teacher/replay/pipeline、review gate、s2配置、层级README、S2来源/操作文档。所有自主模块提供说明，目录README登记；模型/缓存/生成日志不作新框架锁。没有更换verl/Torch/Transformers或SFT/RL实现。

**S2未整阶段完成**：小流水线已经有真实教师正/负回放证据，但人工抽检/身份与官方映射待签，独立语义复核状态需见后续实际结果；正式数量远未达目标。下一步等待用户稍后真实人工裁决，再按训练pilot诊断改检索/完善任务品类与事实来源，质量通过后扩充并完成至少200条真实人工抽检。禁止以工程脚本、复制数据或程序签核代替。实际human JSON收到后用`s2-audit --reviews`评估，不修改旧包；修改来源/模板/官方边界必须重建新revision。不进入S3。

## S2 首轮历史：代码与离线 pilot（当时缺密钥）

用户授权继续S2，并明确让agent先选择教师、在文档醒目标注便于修改。本轮已按AGENTS→PLAN→PROGRESS读取，S2操作文件缺失时先建立并读取范围；仅实现S2，没有实现S3训练。

### 暂定教师与配置入口

**由Codex暂选 `deepseek-flash`，关闭thinking，可修改 [configs/s2-teacher.json](configs/s2-teacher.json)。** 这是低成本工具采集起点，未实测为项目最优。官方2026-10-22文档映射为DeepSeek-V4.1-Flash-1017；该别名会漂移，actual model_revision仍null，不将网页映射当不可变pin。base_url为`https://api.deepseek.com`；默认最多80请求、2 USD估算预算、每请求预留0.025 USD，峰值未命中输入0.30/输出1.20 USD每百万token。模型/价格/协议依据与原HTML留证见[S2来源审计](docs/s2-source-audit.md)。

密钥独立放项目 `.secrets/deepseek_api_key`（已gitignore），或配置改env_var（两者选一）。当前不存在有效配置凭据，实际入口在发请求前停止，`status=blocked/validation_level=not_run_missing_credentials`。**外部教师请求0、真实专家成功0、人工签核0、独立8B复核0**。HTTP loopback测试不是外部教师验收；费用按配置价×provider usage估算，新请求费用排除本地缓存重复使用，真实账单字段保持null。

### 完成的代码与真实小样本

- `data.sources`：真实原字段/原句/raw哈希、USD及g/kg/lb/oz/W数值校验，缺失/冲突拒收。`pipeline.verify_raw_artifact`进一步将每条摘录绑定到原始rows.json行号与文件SHA，修改raw并重算自哈希也不能冒充原始下载内容。
- `data.split`：先把家族/品牌型号/显式近重复/规范标题/MinHash+精确Jaccard并为连通簇，再固定seed0整簇划分。已提供官方ID/家族/型号/标题命中整簇quarantine。词项余弦与受控同义词只作为人工语义候选，不称独立模型复核通过。
- `data.builder`：先在完整检索split求全部合法解，再渲染英文请求、画像、确定性澄清；兄弟root/parent/pair同split。反事实只改一条约束值且合法集非空/不相交；改写单列、当前表达增强0。最终base与cf再次审查跨split同定义重复。
- `data.teacher/replay`：策略只见公开observation/schema/对话；真实工具执行、逐动作重放比对观测/事件/奖励/公共工具ID/请求响应/状态哈希。网络客户端独立密钥、显式执行、持久限额锁、缓存身份绑定、原响应脱敏留存、不自动重发计费不确定请求。工程策略/工程来源均禁止专家导出。
- `data.review/pipeline`：生成hash绑定的人工、家族、语义待审队列；重新回放后按真实审核记录评估放行。人工reject/冲突、过期审核、独立模型分歧未裁决均withheld；需真实人工accept裁决才能解除模型分歧门槛。不写虚构审核记录、不自动开始训练。
- S1 Catalog兼容扩展：原生brand/store优先来源字段、旧夹具family兜底；默认任务加载仍只train/dev，封存须显式开关，教师迭代器仅train。S0/S1原82项回归全部保留通过。

真实来源固定HF **`2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e`**，Parquet首rowgroup1000条选定列，实传 **1,222,800 bytes**；保留12个办公设备原始摘录，8个有可信颜色。只核验实际Range和选定列JSON哈希，未本地验证整个219,918,692-byte源片LFS SHA，也未下载26.9GB官方商品库。源价格是历史采集价，不是当前报价。代码MIT与Amazon研究数据条款分开记录。

官方目标metadata索引来自固定ECom commit `97eff345811fdf652a2135d38d874f2932e11702`，只读取target_product商品ID/标题/结构化Brand/明确型号，不读取query/persona/rubric作为训练输入。662任务得到660唯一ID、660标题、558保守整品牌家族、420品牌型号；659目标有Brand、3个缺品牌仍待审，metadata_complete=false。Logitech/Samsung/Dell/HP四条pilot商品因品牌重合进入quarantine，未以“ID不重合”代替家族隔离。

最终真实数据 **`s2-ee9902b8fc67ad1b39533598`**：原12商品，quarantine4，保留8（产品train/dev/sealed=7/1/0）；base5+cf2=7任务（7/0/0），2对反事实；固定dev商品缺颜色所以未造开发任务，没有换seed补数。工程数据 **`s2-3321fd0522d817eee8ae8e62`**：9个虚构商品，base9+cf3=12任务（7/4/1），3对反事实。后者只验证工程，不属于正式训练集。

### 实际命令、机器、结果与日志

学校Linux `A6000`，项目`.venv-cpu/bin/python`→`.tools/python` Python3.11.16；SQLite3.53.1；普通流程仅标准库。源Parquet抽取单次用`.venv-gpu`已有CPU PyArrow19.0.1并隐藏GPU，未import Torch/vLLM或创建CUDA上下文。无新依赖安装、无新lock、无模型下载、无教师费用或GPU训练证据。

| 命令/动作 | 实际结果 | 日志 |
| --- | --- | --- |
| `PYTHONPATH=src .venv-cpu/bin/python scripts/run_cpu_tests.py --stage S2 --config configs/s2.json --output logs/s2-20261022/tests-v1` | **136项，0失败/错误/跳过**；S0/S1旧82+S2新54（sources11、split14、teacher16、builder13）；含真实本地HTTP及真实SQLite | [unittest.log](logs/s2-20261022/tests-v1/unittest.log)、result.json/run.json；03:58:56–03:59:11+08:00 |
| `s2-build --config configs/s2.json --output logs/s2-20261022/build-real-final` | CPU构建通过；真实来源、排除/分组/可行性/反事实/manifest/审核门槛留存 | [report](logs/s2-20261022/build-real-final/report.json)、dataset/；03:58:53–03:59:06 |
| `s2-build --config configs/s2-engineering.json --output logs/s2-20261022/build-engineering-final` | CPU构建通过；工程来源明确标记 | build-engineering-final/；03:58:53–03:59:06 |
| `s2-collect --config configs/s2.json --dataset logs/s2-20261022/build-real-final/dataset --output logs/s2-20261022/collect-real-engineering-final --engineering --limit 2` | **2/2回放接收**，14/16次真实工具调用，expert_candidates=0 | [report](logs/s2-20261022/collect-real-engineering-final/report.json)、episodes/、accept-reject-ledger.json；03:59:25 |
| 同上改为engineering配置/build-engineering-final，输出collect-fixture-engineering-final | **2/2回放接收**，9/7次真实调用，专家候选0 | collect-fixture-engineering-final/；03:59:25 |
| `s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/s2-20261022/build-real-final/dataset --output logs/s2-20261022/teacher-credentials-final --execute-api --limit 1` | **blocked**，退出1，缺key在发送前停止；无HTTP请求/响应，不算教师失败或通过 | [report](logs/s2-20261022/teacher-credentials-final/report.json)、失败episode/ledger、run.json；03:59:25 |
| `s2-audit --dataset logs/s2-20261022/build-real-final/dataset --collection logs/s2-20261022/collect-real-engineering-final --output logs/s2-20261022/release-audit-final` | 审计执行通过、2条重放接收；**发布withheld，stage_complete=false** | [release-decision](logs/s2-20261022/release-audit-final/release-decision.json)、report/run.json；04:00:21 |

表内CLI缩写均以前缀 `PYTHONPATH=src .venv-cpu/bin/python -m procure_rl` 运行，完整实际argv/配置/source SHA见各run.json；换新输出目录即可复跑。核验源码、测试、fixture、模型默认配置、库和产物一致性见`logs/s2-20261022/handoff-audit.json`。真实教师默认选择的提示与修改入口在根README、configs README、S2操作文档三处醒目记录。

### 修改文件、失败与限制

新增`src/procure_rl/data/{__init__,sources,split,builder,teacher,replay,review,pipeline}.py`及README；`tests/test_data_{sources,split,teacher,builder}.py`；`configs/s2.json/s2-engineering.json/s2-teacher.json`；`fixtures/s2`真实摘录/官方索引/README；`scripts/data/fetch_amazon_pilot.py`及README、`scripts/run_cpu_tests.py`；S2阶段与来源审计；来源字节和最终运行日志。修改CLI/runtime说明、S1 Catalog兼容接口、各层README/本PROGRESS；`.gitignore`将`data/`锚定为`/data/`避免误忽略自主data代码，另排除.secrets；CPU依赖说明仍零外部包。PLAN算法与GPU依赖不变。

早期网络沙箱、HF viewer404/501和旧UCSD链接404保留，不称数据不可用；改固定revision有界Parquet Range成功。源Color语义异常不转成颜色事实。教师测试首轮本机socket受限、随后本地代理未绕过失败；允许本机临时server并显式绕过loopback代理后通过，原失败/复验日志在teacher-development/。新正式全量测试136项无失败；这些loopback运行不访问外部API。

代码审阅修正了：只按anchor标题子池求解漏掉真实catalog候选；cf生成后的跨split重复；工程源搭远程教师仍可能误标专家；env/空key/双凭据来源错误状态；人工reject/conflict门槛；原始摘录与原rows绑定；缓存费用不重复计算。均在最终代码/测试或源审计中留证。历史`*-v1`构建/采集使用ID-only排除表，4个后续应隔离品牌当时仅工程运行且未放行；原索引副本保留，最终不沿用旧数据包。

### 当前阻塞与可直接执行的下一步

**不能把S2整阶段写成完成。** 代码/CPU小流水线通过，但仍需：有效教师密钥与2条真实教师工具轨迹验收；3个官方缺品牌目标与近家族映射审核；商品身份、人工抽检至少200条及全部分歧裁决；独立语义复核。当前pilot不足正式数量且没有真实专家，正式release withheld，S3不启动。当前没有本项目GPU任务、训练任务或付费实例。

密钥写入`.secrets/deepseek_api_key`后可直接执行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/s2-20261022/build-real-final/dataset --output logs/my-s2-real-teacher --cache-directory .cache/s2-teacher --execute-api --limit 2
```

检查格式/真实回放/估算费用后，按[S2操作](docs/stages/S2.md)完成人工与独立模型复核，小规模验收后再扩量。审核另存JSON供`s2-audit --reviews`，不要修改已哈希数据包；改来源/模板/排除规则须建新revision。1600/200/400、100对与600专家均为未达目标，报告实际数，不用工程轨迹填充。

## S1 历史：实施、结果与交接

用户已明确授权从完成的 S0 继续 S1。开始依次读取 AGENTS→PLAN→PROGRESS；发现 `S1.md` 尚未建立后先建立并读取实施范围，再实现。未扩大到 S2 或训练。

- **固定上游**：EComAgentBench commit `97eff345811fdf652a2135d38d874f2932e11702`，原样75文件，归档SHA256 `df5c96b2de11f336ac5c2a90a6a547286765fc96c1d956419b327fa96ecdfcd3`。代码MIT与原始数据研究用途分别审计。官方662条只核记录数与状态，未用目标/rubric设计奖励；完整官方26.9GB库及LLM judge未运行。
- **环境与工具**：`src/procure_rl/env/` 实际加载核验哈希的11个原始模块，运行九个原生工具，不启用python_execute；项目层只覆盖只读连接，新增JSON协议、独立会话、预算、证据、事件与快照。每个split物理独立SQLite文件，运行时校验哈希、ro/immutable/query_only，无sidecar写入。
- **固定工程数据**：`fixtures/s1` revision `s1-fixture-v1`，9个虚构商品、45证据、2英文任务、7候选真值。train两个合法解、屏数与供电反例；dev预算与接口反例。供电事实仅从真实review检索返回后附引用。独立预期矩阵由协作agent编写并逐项核对，未有额外人工签核；不是S2数据集、专家采集或模型结果。
- **验证器与回放**：终局事实硬约束奖励与证据交付诊断分开；首次隐藏/证据正预算0.4/0.6，同事实更换候选不刷新，无效-0.05/完全重复无进展-0.02。快照保存澄清、覆盖集、历史、剩余预算与RNG，恢复先真实重放比较后替换；同动作观测、事件和预算一致，并发会话隔离。
- **结构化轨迹**：显式保存steps、step_rewards、verifier_events、policy_version/seed/revision。S1未token化，turn_spans空并标记原因，不冒充S3 token对齐。在线Agent只接收observation/schema，快照、私有任务和诊断不进入prompt。

### 最终命令、机器与日志

机器 `A6000`，Linux6.8.0-90/glibc2.35；明确使用项目 `.venv-cpu/bin/python` → `.tools/python` 的 Python3.11.16，SQLite3.53.1，仅标准库。没有安装新依赖、修改GPU环境锁、调用系统Python/Toolkit/GCC、创建CUDA上下文、下载模型或调用教师API。data revision `s1-fixture-v1`，脚本策略 `scripted-s1-v1`，验收seed0；model/checkpoint均null。

| 命令/动作 | 实际结果 | 证据 |
| --- | --- | --- |
| `PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/s1-20261022/acceptance-final` | **27/27 passed**，退出0，7条候选脚本与快照、并发隔离、只读split、无效/重复/40步预算 | [report.json](logs/s1-20261022/acceptance-final/report.json)、`report.md`、`run.json/run.log`、`catalog/manifest.json`、`trajectories/` |
| `unittest.defaultTestLoader.discover('tests')` + `TextTestRunner(verbosity=2)`（等价命令 `PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -v`；精确包装脚本随日志保留） | **82项，0失败/错误/跳过**：S0旧39 + S1新43（upstream5、verifier21、session17） | [unittest.log](logs/s1-20261022/tests-final/unittest.log)、`result.json`、`run.json`、`command-source.txt` |
| 原生来源核验 | git ls-remote固定commit、codeload固定URL；75文件manifest一致，必要11文件运行前再校验 | [上游审计](docs/ecom-upstream-audit.md)、`third_party/.../UPSTREAM-MANIFEST.json` |

最终两项均开始于2026-10-22 03:06:53+08:00、结束于03:06:54+08:00。运行清单保存真实机器、解释器、源文件/配置/夹具哈希；配置SHA256 `850c7007272fd097035725b97651a9d57b71a9aad0f5ae29c96d8309c8f2c962`。首轮`acceptance-v1`亦27/27，保留历史，不覆盖最终源状态。

### 修改文件与失败记录

新增：`src/procure_rl/env/{__init__,catalog,protocol,upstream,session,verifier,smoke}.py`及README；`tests/test_{session,upstream,verifier}.py`；`configs/s1.json`；`fixtures/s1/{catalog,tasks,expectations}.json`及两层README；`third_party/README.md`与固定上游副本/manifest；`docs/ecom-upstream-audit.md`、`docs/stages/S1.md`；`logs/s1-20261022/`运行产物与交接审计。

修改：CLI `src/procure_rl/__main__.py`增加s1-smoke；runtime增加显式stage（旧入口仍默认S0）；根/源码/包/测试/config/docs/stages/logs的README与本PROGRESS同步。PLAN算法与核心GPU依赖不变，无新lock。

开发中发现并修复：原生reasoning误传给规范推荐验证器导致交付诊断失败；原生超长/耗尽澄清返回user_response而非error，现从结构化计数/长度标无效；非有限dict动作占位与深JSON异常导致不可回放/漏计预算，现规范化并记录；过大页码触发SQLite INTEGER溢出，现协议限制整数范围。均有最终回归覆盖。并行初次单测曾因session文件尚未落地而导入失败，完成文件后通过；不是依赖或上游兼容失败。网络API限流/失败与git+codeload恢复见上游审计。开发记录见`development-notes.json`，未保存的早期精确时间或原始stderr不补造。

### 阶段结论与下一步

**S1代码完成 / 学校Linux CPU固定小样本验收通过；本阶段无剩余阻塞。** 未运行完整官方数据/评分、额外人工签核、80步压力任务、真实模型多轮/LoRA同步/GPU训练；不以本次脚本与数值测试代替后续验收。S1不存在需等待GPU的必验项。

本轮停止在S1。下一次用户授权S2时先读AGENTS→PLAN→PROGRESS→S1交接，建立并读取S2操作文档，再实现小规模事实先行/家族划分/去重/反事实/教师采集与真实回放过滤，先验收小流水线再扩规模。可立即复跑的S1命令见上表和[S1操作](docs/stages/S1.md)，更换输出目录即可。无训练、教师调用、付费资源或本项目GPU进程启动。

## S0 历史：已完成的工程与文档

- 唯一现行[PLAN.md](PLAN.md)按修订稿（2）和用户后续指令合并，保留仍适用的论文、数据、算法公式、B0–B6与S8细节。两份原稿原样归档到[docs/archive](docs/archive/README.md)，manifest保留字节数与SHA256。
- [AGENTS.md](AGENTS.md)要求每次依次读取AGENTS、PLAN、PROGRESS和当前阶段文档；根README、[S0操作](docs/stages/S0.md)、各自主维护代码目录的逐文件README已建立。没有用空模块表示后续阶段完成。
- `src/procure_rl/`实现CLI、配置schema、运行清单/哈希、只读doctor、25项隔离检查和授权GPU探针；`tests/`覆盖配置、失败记录、进程隔离/回收、UUID与PCI映射。配置文件是项目规划schema，**不是已验证verl训练配置**。
- uv引导项目独立Python3.11.16到`.tools/python`，建立`.venv-cpu`、`.venv-gpu`与`.venv-toolchain`；所有Python执行使用项目解释器。CPU工具只用标准库，GPU包独立安装。
- `scripts/with_proxy.py`仅提取用户已授权的`proxy_on`函数为单命令启用代理，不执行整个bashrc/conda初始化，不输出代理凭据。`scripts/toolchain/cc,cxx`仅调用项目Zig，不回落系统GCC/nvcc。
- 候选解析、安装、`pip check`、隐藏GPU导入和真实GPU结果分别留证；传递依赖修复不改四个核心版本。必要验收通过后已生成S0范围的204包环境锁、独立工具链锁、实装快照与验证manifest；它们不代表全栈训练兼容。

## S0 历史：实际机器、版本与授权

| 项目 | 实测事实与边界 |
| --- | --- |
| OS / CPU / 内存 | Ubuntu22.04.5、glibc2.35；2×Xeon Silver4214，48逻辑CPU；主机内存约502.6GiB |
| 磁盘 / 共享内存 | 项目卷可用约1.8TiB，`/dev/shm`约251.3GiB；观察值不代表个人配额 |
| GPU / 拓扑 | 4×A6000（49140MiB）+4×3090（24576MiB）；A6000索引1/4/5/7，4/5/7互为PIX；PIX不等于NVLink |
| 驱动 / runtime | 驱动560.35.03；nvidia-smi标签CUDA12.6；**实际Torch runtime12.6、NCCL2.26.2**，分别有GPU证据 |
| Toolkit / 编译器 | 系统CUDA10.2/11.3/11.7只列路径，未执行系统nvcc或GCC。项目没有完整Toolkit；Ziglang0.17.0独立C编译/链接/加载通过，必要系统驱动库只由项目链接使用 |
| 真实依赖 | Python3.11.16；verl0.6.1 commit `d62da4950573d7a4b7ef2362337952e7ab59e78d`；Torch2.7.1+cu126（CXX11 ABI=True）；vLLM0.10.0+cu126；Transformers4.53.2；共204包，依赖声明检查通过 |
| 补充包 | FlashAttention2.8.0.post2官方CUDA12/Torch2.7/ABITrue构建；xformers0.0.31；PEFT0.16.0、Accelerate1.8.1、TorchData0.11.0；其他实际版本见metadata与快照 |
| Git | 初始仅两份计划和隐藏只读目录；`.git`为空且非有效仓库，查询退出128；未修改只读目录，以源码SHA256追溯 |

GPU授权来自本次对话，记录于`logs/s0-20261022T0145+0800/allocation.json`：

| 物理编号 | UUID | 实际范围 |
| --- | --- | --- |
| 5 | `GPU-2e81c395-ac38-bfde-adba-34f3d967f7af` | 双卡计算；最终单卡注意力与推理选择此卡（执行前余量更多） |
| 7 | `GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03` | 双卡计算；历史FlashAttention2.8.3小内核 |
| 4 | `GPU-f772dd3f-e279-8cdc-62dd-7b39740b2063` | 只读拓扑，未计算；用户三卡附加授权以不占显存为条件，真实CUDA/P2P/NCCL会占显存 |

只在获准5/7中依据即时余量选卡，没有依据空闲显存认领其他卡，没有终止或修改他人进程。运行时先核验真实UUID；vLLM0.10.0额外需要只读NVML/PCI索引转换，授权输入仍是UUID。动态显存/进程/空间只对应采集时刻。

## S0 历史：命令、结果与日志

本次接续日志根：[logs/s0-20261022T0145+0800](logs/s0-20261022T0145+0800/)。完整执行命令与缓存/代理/恢复办法见[S0](docs/stages/S0.md)，每个CLI运行保留机器、解释器、源文件哈希、实际argv和时间。

| 操作 | 实际结果 | 相对接续日志根的位置 |
| --- | --- | --- |
| `doctor --output …/doctor` | 主机只读硬件/驱动/拓扑/进程存在性检查完成；Git失败如实记录 | `doctor/report.json`、`report.md`、`run.json` |
| uv候选解析/安装 | 核心版本保持；v2→v3→v4的解析、安装与修正均保留；最终204包实装 | `dependencies/gpu-resolved-v*-candidate.txt`、`resolve*.log`、`install*.log` |
| `uv pip check --python .venv-gpu/bin/python` | 退出0，204包声明一致；此结果单独不证明运行兼容 | `dependencies/pip-check-final.log` |
| `check-environment --python .venv-gpu/bin/python --timeout 120` | **25/25通过**；GPU隐藏，禁止外部程序执行；含FSDP2/LoRA/AgentLoop实际API导入，未执行训练 | `imports-final/report.json`、`report.md`、`probes/`、`run.json` |
| `unittest discover -s tests -v` | **39项CPU测试通过，0失败/错误/跳过**；包含mock，不是GPU验收 | `tests-handoff/unittest.log`、`result.json`、`run.json` |
| 项目Zig编译、Python.h与驱动链接加载 | 退出0，C调用返回42；不调用驱动函数、不创建CUDA上下文 | `toolchain/compile.json`、`compiler-smoke.so`、`pip-check.log`；`driver-links.json` |
| GPU5/7 `--probe torch --probe nccl` | **实际通过**：两卡BF16前反向；4096bytes双向peer copy；2rank/16float NCCL all-reduce正确 | `gpu-pair/report.json`、`run.json` |
| GPU5 `--probe attention` | **实际通过**：FlashAttention2.8.0.post2，BF16小Q/K/V前反向与有限性 | `gpu-final/report.json`中的`checks.attention`；该次整体因vLLM失败而失败 |
| GPU5 `--probe vllm` | 首轮UUID解析失败；适配后的复验**通过**，生成`OK.`，3个token（含结束token），正常stop | 首轮`gpu-final/report.json`；复验`gpu-vllm-final/` |
| 模型下载/完整性 | Qwen3-0.6B固定revision八文件完成，权重1,503,300,328bytes，官方SHA256与本地一致 | `model-source*.json`、`model-download.json`、`model-verified.json` |
| NVML编号映射 | 只读确认UUID、NVML index与PCI顺序；没有创建CUDA上下文 | `nvml-pci-mapping.json` |

这些通信是正确性检查，**没有带宽、吞吐或三卡实测结论**。BF16峰值分配量不包含全部CUDA上下文开销。GPU检查只覆盖请求子集，报告明确保留`candidate_stack_compatibility=not_established`。

首次工作日志`logs/s0-20261022T0056+0800/`原样保留：唯一计划/归档、独立Python引导、配置检查、主机只读盘点、当时10项CPU测试和未完成下载。旧测试数量与未安装状态是历史事实，不能代表当前状态；旧`handoff-audit.json`仅适用当时范围。

## S0 历史：失败与修复（原始证据保留）

- 网络/沙箱：早期NVML退出9、Python下载网络失败，经主机执行上下文及授权代理恢复；没有据此判断依赖冲突。前轮下载中断退出130保留。没有修改系统驱动/Toolkit。
- 来源/构建：默认vLLM wheel不是目标cu126，改用官方cu126 URL；Torch全局额外索引导致普通包候选偏移，改为四个CUDA wheel明确URL。只允许已审阅的纯Python `verl/pylatexenc/antlr4-python3-runtime`源码构建，其余二进制。
- 数据依赖：实装PyArrow26要求NumPy2，与本项目NumPy1.26冲突；修订PyArrow19.0.1、datasets3.6.0、pandas2.2.3，保存v3解析/安装。
- Hydra/构建依赖：旧Hydra/OmegaConf缺少所需API，setuptools84移除`pkg_resources`；修订Hydra1.3.2、OmegaConf2.3.0、ANTLR4.9.3与setuptools78.1.0，保存v4记录。
- 探针：初版用RuntimeError阻断NumPy可选`lscpu`探测，导致正常回退失效；改为仍禁止执行、以FileNotFoundError表达工具不可用并记录名称。异步server探针曾误要求新版类名，已按固定0.6.1改为源码实际三个接口。相关CPU测试与失败日志保留。
- FlashAttention：2.8.3虽在GPU7通过小内核，但超出xformers0.0.31前三段版本范围。改官方2.8.0.post2匹配wheel，实际SHA256为`8ed71ac092f80b079d2e6043b769135904d6e834916cb6da7d372b394581447b`；导入和GPU5小内核通过，没有忽略版本检查。旧wheel与失败记录保留。
- vLLM：0.10.0 NVML接口把可见性条目转int，首轮不能接受UUID。项目探针先核验CUDA UUID，再通过vLLM内置NVML只读核对PCI顺序并转换授权卡数字编号；不改上游、不增加顶级pynvml依赖。`communicate`异常回收缺口已修复并CPU回归通过；实际推理复验已通过，结果和原失败分开保留。

## S0 历史：实际环境锁与已知限制

以下四份产物在安装、pip check、必要真实GPU检查通过后生成，版本与哈希见[validation-s0.json](requirements/validation-s0.json)：

- [linux-py311-cu126-s0.lock](requirements/linux-py311-cu126-s0.lock)：204包实际版本及明确来源，适用本机Linux x86_64/Python3.11/cu126；FA本地wheel映射回内容SHA已核对的官方URL，vLLM恢复候选URL哈希。
- [toolchain-s0.lock](requirements/toolchain-s0.lock)：独立Zig0.17.0；通过C/Python.h/驱动链接与本轮vLLM实际C launcher，未验证完整Torch Inductor C++。
- [installed-snapshot.txt](requirements/installed-snapshot.txt)：原样实装快照，含FA本地文件来源；跨机器重建使用上面的公共URL锁。
- [validation-s0.json](requirements/validation-s0.json)：机器、版本、源commit、GPU/模型、证据、产物哈希和未验证项。所有包并非均有独立下载档案SHA；installed-metadata保存的是安装RECORD摘要，不能冒充wheel档案哈希。

没有在第二个全新环境另做安装重现。vLLM运行有项目Zig的POSIX宏重定义和上游进程组析构警告，但推理、引擎退出正常，最终只读检查无本项目GPU进程遗留；原stderr保留，没有删除警告或修改上游。

## S0 历史：模型、配置与验证边界

本地模型`Qwen/Qwen3-0.6B` revision **`c1899de289a04d12100db370d81485cdf75e47ca`**；权重SHA256 **`f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b`**。模型路径为`models/Qwen3-0.6B/<revision>`。GPU探针种子0，单提示关闭thinking、BF16、TP1、上下文512、并发1、最多16生成token、eager、关闭编译优化、显存比例0.2；正式2K–12K、多轮和训练配置未验证。

没有训练数据revision、策略版本、optimizer、checkpoint、训练曲线或教师API调用。4B主实验与8B诊断规则保持PLAN，尚未下载或训练。导入通过和最小推理通过均不能替代S3/S4的真实多轮、LoRA同步、FSDP2训练、连续5次更新和保存恢复验收。

## S0 历史：当时的下一步（现已完成 S1）

1. 本次S0已完成，停止在阶段边界；已有独立环境保留供接续，无需重装。
2. 下一次推进S1时先读AGENTS→PLAN→PROGRESS→当前S0操作文档；进入S1再建立`docs/stages/S1.md`，核验EComAgentBench准确revision/许可证，实施固定小样本CPU环境、会话、工具、快照、终局/过程验证器。S1目前没有实施。
3. 后续GPU任务继续限定获准5/7；设备协调情况改变时更新UUID授权记录，执行前复查容量。首次在另一台机器/全新环境重建锁后重跑S0相应检查，不假定可迁移兼容。

当前没有外部信息阻塞；设备5/7和代理授权已明确。本轮全部下载、安装和GPU验收均已结束，没有本项目遗留GPU进程、训练任务或付费外部资源。清理证据`gpu-cleanup.json`；S0交接一致性结果`handoff-audit.json`。
