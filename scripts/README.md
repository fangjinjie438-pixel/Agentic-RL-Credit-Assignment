# 项目脚本

| 子目录 | 用途 |
| --- | --- |
| [data](data/README.md) | S2 固定来源的有界 HTTP Range 元数据抽取；隐藏 GPU，仅一次性来源获取依赖已装 PyArrow |
| [toolchain](toolchain/README.md) | 项目独立 C/C++ 编译器入口，禁止回落系统 GCC/Toolkit |

| 文件 | 用途与执行 |
| --- | --- |
| `run_cpu_tests.py` | S0–S2标准库unittest执行器，隐藏GPU，输入stage/config/新output目录，输出`unittest.log`、`result.json`、`run.json/run.log`及源/测试/配置/夹具哈希。完整命令：`PYTHONPATH=src .venv-cpu/bin/python scripts/run_cpu_tests.py --stage S2 --config configs/s2.json --output logs/my-s2-tests`。不访问外部教师；loopback HTTP协议测试需允许临时本地socket，最终数量与状态见PROGRESS。 |
| `with_proxy.py` | 通过用户授权的 `proxy_on` 为单个命令启用代理；仅读取该函数，不执行整个shell初始化（避免全局conda等工具），不输出函数或代理凭据。使用项目CPU解释器：`.venv-cpu/bin/python scripts/with_proxy.py -- uv …`。输入命令参数，输出为命令自身输出与退出状态。 |

Python 入口使用项目 `.venv-cpu` 或 `.venv-gpu`，缓存位于项目内。具体执行结果见 PROGRESS 和 S0 操作文档。代理包装仅适用于rc中独立定义的`proxy_on()`；匹配不到明确失败，改在用户终端手动启用，不执行其他初始化。

输出目录已存在时换新目录，保留原测试日志；依赖缺失先按项目README恢复独立环境，不调用系统Python。来源提取的PyArrow只用于已有`.venv-gpu`中的CPU解析，必须隐藏GPU；离线数据构建/测试仍使用`.venv-cpu`，不依赖PyArrow。完整来源命令与当前未完成验收见[来源审计](../docs/s2-source-audit.md)及[S2阶段](../docs/stages/S2.md)。
