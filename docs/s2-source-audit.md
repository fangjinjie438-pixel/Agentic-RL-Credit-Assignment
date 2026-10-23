# S2 来源与教师文档核验

核验日期：2026-10-22（Asia/Shanghai）。来源获取时取得12条真实商品摘录、完成离线归一化与只读SQLite验证；当时只查教师文档。用户配置密钥后的接续已实际调用DeepSeek两批共72次，v2接收1/2，缓存重现一致，估算0.0754485 USD、账单未知。原始响应/usage在 `logs/s2-20261022-api/`，独立8B状态见PROGRESS。数据不因归一化或API执行成功成为已通过人工审核的正式训练集。

## 固定真实数据及字节证据

原始来源为 [McAuley-Lab/Amazon-Reviews-2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023) 的 `raw_meta_Electronics`。通过已授权的 `scripts/with_proxy.py` 只读代理实际查询 HF API，固定 revision **`2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e`**。API 响应原样位于 `logs/s2-source-audit/hf-api.json`（75,317 bytes，SHA256 `a8c718935851da8f1ac54000392e987dabdd0276f60d8b3dfc009e46d6b9ce88`）。官方固定 README 存为 `amazon-card.md`，SHA256 `98564a55cfca48704ee5c9d30df11f5a0c24d00e19c53c4ec7fb34abcec5ae0f`；原卡明确 `price` 是采集时美元价格。

实际下载 URL 为 [固定 Parquet](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e/raw_meta_Electronics/full-00000-of-00010.parquet)。源文件大小 219,918,692 bytes；HF Tree API 宣告 LFS SHA256 `116fe3967889da3d2fd1f5785f46532955d7c952649aa8eebf6eb6434bb9db16`。**没有下载完整文件，不能声称本地验证了完整 LFS SHA。** 本轮通过 HTTP `Range` 读取 Parquet footer 及首 row group 所需列，合计 **1,222,800 bytes**，解出 1,000 条原始记录的 `main_category/title/price/store/categories/details/parent_asin` 列。每次请求要求状态 206、严格起始偏移及长度，累计上限 256 MiB。

证据位于 `logs/s2-source-parquet-v1/`：`range-*.bin` 保存实际传输字节，`ranges.json` 保存每段起止位置/URL/字节/SHA；`rows.json` 保存 PyArrow 解出的原始选定列；`executed-source.py` 是实际执行的脚本副本；`execution-summary.json` 保存命令、机器、解释器、依赖、所有产物哈希。精确脚本启动时间当时没有独立记录，已明确写 null；不推断倒填。`ranges.json` 的 retrieved_at 是该清单最后写入 UTC 时间。

来源获取命令（**已实际运行**；学校 Linux `A6000`）：

```bash
CUDA_VISIBLE_DEVICES='' .venv-cpu/bin/python scripts/with_proxy.py -- .venv-gpu/bin/python scripts/data/fetch_amazon_pilot.py --output logs/s2-source-parquet-v1
```

仅导入 `.venv-gpu` 已安装的 PyArrow 19.0.1 和 Python 标准库；该虚拟环境路径用于已有 CPU Parquet 解析包，不导入 Torch、vLLM 或 GPU 库。普通 S2 离线流水线与测试仍用 `.venv-cpu`、只依赖标准库。

`fixtures/s2/amazon-electronics.json` 保留其中 12 条办公电子设备：LENTION 扩展坞，KECOP、Macally、Mafiti、EDJO、RunElves、Logitech 键盘/键鼠组合，Samsung/Thinlerain 显示器，HP/Dell 笔记本，Netgear 路由器。选中行号为 47、176、182、185、429、514、630、691、762、808、869、895。所有记录保留真实 source_row_index、原始 details JSON 字符串和原记录 SHA；规格只从结构化字段摘录，不从标题推断。12 条均有美元价格与重量；8 条有明确颜色字段。HP 的原始 Color 为 `Non-Touchsceen`，Mafiti 的原始 Color 为组合描述，均没有转为颜色约束。其余原始疑点保留进入人工审核；本轮没有 200 条人工签核。

`normalize_records(records, source=...)` 验证原始记录哈希、原字段路径、原句逐字匹配、值与单位一致，使用 Decimal 进行 USD/g/kg/lb/oz/W 归一化，拒绝缺失价格、无两项规格、重复/冲突字段、未知单位和不明确币种。输出 S1 product/evidence 结构，不赋 split；品牌/型号只读原字段，默认把整品牌作为保守 family，并标记人工待确认。商品关联的更细家族和语义疑点仍需要人工。原始价格是历史抓取价格，不能当作当前报价。

## 数据许可与官方测试隔离

EComAgentBench 固定 [MIT LICENSE](https://raw.githubusercontent.com/Morizeyao/EComAgentBench_/97eff345811fdf652a2135d38d874f2932e11702/LICENSE) 仅适用代码。[Amazon 数据维护者的官方许可说明](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/discussions/1) 明确表示无权替原始数据分配许可，提供数据主要为研究目的。因此本项目没有把 MIT 传播到商品内容，也没有宣称获得商品数据的通用再许可或商业授权；本轮仅本地研究 pilot。

`fixtures/s2/official-exclusions.json` 最初只读 `target_product.product_id`；初版保留于 `logs/s2-source-audit/official-exclusions-id-only.json`。随后确认固定 benchmark 已附目标商品 metadata，按 PLAN 仅用于 quarantine 补读 `target_product.title`、`target_product.details.Brand` 与明确的 `Item model number`/`Model Number`（大小写规范化），不使用 Compatible Phone Models/CPU Model 等兼容对象字段。

实际执行 `.venv-cpu/bin/python /tmp/s2-extract-official-metadata.py`，可复用副本 `logs/s2-source-audit/extract-official-metadata.py`；精确命令、起止时间、机器/解释器、源和输出 SHA 见 `official-metadata-extraction.json`。来源仍为固定 commit `97eff345811fdf652a2135d38d874f2932e11702`，文件 SHA256 `c6585d7adade0bf898dcc6b5377fb4534a699b874bd21ec796acfa96547c9b52`。662 条任务中659条有非空Brand，423条同时有明确model number；索引去重得到 **660商品ID、660标题、558整品牌family、420品牌型号组合**。whole-brand 是保守排除方法，同品牌所有本地候选均不得进入训练检索；它不声称这些商品实际属于同一精细型号家族。

该步骤不访问 query、persona、rubrics 或其他任务内容，不将官方商品标题用于任务表达。12条pilot源的exact-ID交集仍为0，但扩充索引后 **Logitech、Samsung、Dell、HP四条按整品牌进入quarantine**，余8条可作小流水线输入。初版ID-only下的旧运行保留，不能代表新索引边界。

**覆盖仍是部分完成。** `coverage=target_ids_and_available_brand_model_title`，3个缺品牌的官方目标ID记录于 `unknown_family_product_ids`，`metadata_complete=false`。这3个目标的家族待映射，已有metadata的语义近重复也需要人工/独立复核；不因可用元数据已索引就宣称整个官方污染隔离完成。正式训练发布继续保留该gate。

## 教师建议：agent 暂定，可查看修改

按用户本轮授权，建议先用 **`deepseek-flash` non-thinking** 承担英文任务表达与专家工具执行。它是 agent 的暂定工程建议，尚未依据本项目真实采集质量/成本比较确认最优，实际配置以 `configs/s2-teacher.json` 为准。需要复核时可调整配置；`deepseek-v4-pro` 可作为分歧样本可选教师，独立 8B 语义复核仍按 PLAN 保留，未因这一建议视为已完成。

[官方模型/价格页](https://api-docs.deepseek.com/quick_start/pricing/) 本次显示 Flash 别名映射 **DeepSeek-V4.1-Flash-1017**，Pro 为 **DeepSeek-V4-Pro-0813**；Flash 的美元单价（每百万 token）为：缓存命中输入 off-peak/peak 0.003/0.006、未命中输入 0.15/0.30、输出 0.60/1.20。Pro 对应 0.022/0.044、0.66/1.32、1.98/3.96。价格有时段区分并可能调整，实际采集前应复查。Flash 成本较低是本轮建议的依据；不以价格推断在本项目的专家成功率。

[官方工具文档](https://api-docs.deepseek.com/guides/tool_calls/) 使用 OpenAI 格式 function tools，模型先返回 `assistant.tool_calls`，客户端实际执行工具后将 `role=tool`、`tool_call_id` 与 observation 返回，再继续请求。默认 thinking 开启，本项目第一版必须显式传 `thinking: {type: disabled}`；SDK 的写法是 `extra_body`，标准 HTTP 请求中是 JSON 顶层。项目不启用网络搜索或服务端检索工具，教师只调用本地采购环境工具。

[官方思考模式说明](https://api-docs.deepseek.com/guides/thinking_mode/) 说明 thinking 模式的工具回合必须传回完整 `reasoning_content`；本轮建议关闭 thinking，降低采集与后续 action-only 监督的协议复杂度。严格模式需独立 Beta base URL 和受限 JSON schema，本轮不默认为其已验证；本地 S1 协议仍强制校验教师生成的工具参数。

来源获取时未执行 `/models` 或生成；接续生成现已确认账号可调用 `deepseek-flash`，原始响应 model 同名。别名仍可能漂移，provider system_fingerprint只是另存的观测值，不是已认证的不可变revision；actual model_revision保持null。请求配置、日期、原始响应、usage、收费估计和提示哈希均保留，离线复现优先缓存。价格/工具 HTML 原样存于 `logs/s2-source-audit/deepseek-{pricing,tools}.html`，SHA256 分别 `b856a6e93fa4793ecc8f3fd03a01bb7d8f7572f78a4739da8ce6dbdb09328d66`、`75e870459ba551f018193f65dfe769eb95ec1d7b72523b319370fbecd26faf30`。

缺 Brand 三目标的接续审计只投影 target_product 的身份字段；`logs/s2-official-identity-audit-20261022-v2/identity-audit.json` 保存逐项原字段和佐证。`fixtures/s2/official-exclusions-candidate.json` 增加 Alphaline、EtherealKiller、Reolink Digital 三个保守排除别名，原始unknown_family_product_ids和metadata_complete=false保留；当前s2.json使用该候选，新数据revision `s2-f692f21320912220be59d4a5`。它没有用官方任务表达构建训练需求。

## 失败与恢复记录

首次沙箱内 urllib 访问公开 HTTPS，返回 `URLError: Operation not permitted`；使用既有授权代理并经平台允许的网络执行后访问成功，未输出代理凭据。HF datasets-server 的 first-rows(full) 返回 404，splits 返回 501，原因是该数据集的旧脚本执行格式不被 viewer 支持；官网 README 的 UCSD gzip 原始链接实取 404。这些均未解释为“数据不存在”或静默更换来源，改用同一官方 HF 数据集的固定 Parquet 文件，并限制传输。

元数据摘录第一稿曾因 Thinlerain 没有 Color/Connectivity 导致不足两个规格而退出，随后明确使用其原始 Screen Size/Display Resolution 字段；Mafiti/HP Color 语义异常经审查后不生成该事实。数据发布状态不因该修正变成人工终审。源 URL/机器原始错误已在执行记录中保留；早期请求的单独 stderr 没有文件存档，本文不补造完整日志。

离线验证命令（**已先前通过；最终官方元数据扩充后的结果见 PROGRESS**）：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m unittest discover -s tests -p 'test_data_sources.py' -v
```

覆盖单位/币种、原句/字段/哈希伪造拒收、重复/冲突与缺价格、真实12条 metadata→S1只读 SQLite、官方可用目标元数据 quarantine。最终全量数据流水线/测试证据以 S2 阶段文档和 PROGRESS 的新运行清单为准；此单测不替代教师真实执行、200条人工审核、8B复核或 GPU训练验收。
