# 配置（S0–S2）

| 文件 | 用途、输入输出与调用 |
| --- | --- |
| `s0.json` | S0 CPU schema检查的候选规划：版本、模型角色、GPU默认关闭、未来训练参数；`config.py`读取，不能传给verl/Hydra，不是依赖lock或兼容通过证据 |
| `s1.json` | S1固定虚构夹具、策略版本、种子；`s1-smoke`读取，输出真实环境验收和哈希日志，不是训练配置 |
| `s2.json` | S2真实历史metadata研究pilot；`s2-build`读取原始来源、官方quarantine、seed/split比例、price/query、color/persona、weight/clarification模板。`s2-collect`读取相同工程策略参数；发布门槛独立保留 |
| `s2-engineering.json` | S2离线工程验收；沿用S1虚构商品，先清除旧split再聚类划分，以接口/屏数/供电模板构造任务，永久标记engineering-only，不能作为正式数据 |
| `s2-teacher.json` | 用户授权Codex暂选的可编辑教师建议；`OpenAIHTTPTeacher`读取URL/model/thinking、独立密钥路径、请求/费用预算、估价与文档来源。默认`deepseek-flash`、thinking disabled，尚未用项目真实教师采集质量验证最优 |

CPU开发与学校Linux均在项目根目录运行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-config --config configs/s0.json --output logs/my-config-check
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-build --config configs/s2.json --output logs/my-s2-build
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s2-collect --config configs/s2.json --teacher-config configs/s2-teacher.json --dataset logs/my-s2-build/dataset --engineering --limit 2 --output logs/my-s2-engineering
```

S2构建输出数据包manifest、split只读SQLite、英文任务/反事实、排除/拒收/审核队列与发布门槛；工程采集输出轨迹和真实回放ledger。**真实小流水线构建已实际通过**，最终修订版、测试数量与未执行项见PROGRESS；工程策略不替代真实教师，当前没有正式训练release。

教师`expected_model_revision`是2026-10-22官方文档显示的可变别名映射，真实`model_revision`未知保持null。密钥仅放`.secrets/deepseek_api_key`，不填写到JSON、命令或日志。真实API采集尚未运行；完整显式`--execute-api`、`--cache-only`、`s2-audit --reviews`命令和失败恢复见[data README](../src/procure_rl/data/README.md)。默认2 USD是可改的pilot上限，估算成本不等于供应商账单，也没有进行人民币汇率换算。

全部输出必须为新目录；修改来源、split、模板或教师配置会改变哈希，创建新run保留旧产物。缺密钥记录`not_run_missing_credentials`；无任务检查quarantine/拒收原因；哈希变化重新构建，不绕过校验。本目录不保存GPU设备使用授权，未来GPU执行另记录具体UUID与协调来源。S2官方近家族元数据、200条人工审核、家族确认、独立8B语义复核及真实教师回放门槛分别记录，不能仅凭配置文件标为通过。
