# 配置（S0–S1）

| 文件 | 用途与操作 |
| --- | --- |
| `s0.json` | CPU 工具校验的候选规划数据：版本、模型角色、GPU 计算关闭、未来训练默认参数。`candidate_unverified` 不可提升为 verified；不直接传给 verl/Hydra，不是依赖 lock。由 `src/procure_rl/config.py` 读取。 |
| `s1.json` | S1 CPU 工程验收：夹具路径、脚本策略版本和种子。由 CLI `s1-smoke` 读取并记录配置哈希；不是模型或训练配置。 |

项目根目录运行：

```bash
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl check-config --config configs/s0.json --output logs/my-config-check
PYTHONPATH=src .venv-cpu/bin/python -m procure_rl s1-smoke --config configs/s1.json --output logs/my-s1-acceptance
```

产物是 `validated_config.json` 与运行日志，表示 CPU schema 校验，不表示 GPU 兼容。执行状态见 PROGRESS。本阶段没有已验证的正式训练配置；未来具体 GPU 归属与模型 revision 在新 run 中记录，不能往这个只读配置里填入未经确认的设备。

