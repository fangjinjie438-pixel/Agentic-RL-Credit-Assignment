# 固定工程夹具

本目录保存自主编写、可版本控制的小型工程夹具。它们用于环境协议与验证器验收，不是 S2 训练/开发/封存数据集，也不包含真实商品或官方 benchmark 任务。

| 路径 | 用途、输入输出及调用关系 | 阶段与验证状态 |
| --- | --- | --- |
| [s1/](s1/README.md) | 虚构办公扩展坞事实、英文任务和独立人工真值；环境数据库构建入口读取 `catalog.json`，会话读取 `tasks.json`，验收读取 `expectations.json` | S1 固定 CPU 工程验收；实际运行结果见根 `PROGRESS.md` |

从项目根目录使用独立解释器检查 JSON 语法（CPU 开发与学校 Linux 相同）：

```bash
.venv-cpu/bin/python -m json.tool fixtures/s1/catalog.json > /dev/null
.venv-cpu/bin/python -m json.tool fixtures/s1/tasks.json > /dev/null
.venv-cpu/bin/python -m json.tool fixtures/s1/expectations.json > /dev/null
```

这些命令只验证 JSON 可解析；环境执行、快照和奖励验收使用 [S1 操作文档](../docs/stages/S1.md) 的完整命令。原始夹具保持只读，生成的数据库、轨迹与报告写入新的运行目录。没有 checkpoint；数据库损坏时从固定 JSON 在新目录重建。找不到文件时确认从项目根目录执行。
