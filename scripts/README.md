# 项目脚本

| 子目录 | 用途 |
| --- | --- |
| [toolchain](toolchain/README.md) | 项目独立 C/C++ 编译器入口，禁止回落系统 GCC/Toolkit |

| 文件 | 用途与执行 |
| --- | --- |
| `with_proxy.py` | 通过用户授权的 `proxy_on` 为单个命令启用代理；仅读取该函数，不执行整个shell初始化（避免全局conda等工具），不输出函数或代理凭据。使用项目CPU解释器：`.venv-cpu/bin/python scripts/with_proxy.py -- uv …`。输入命令参数，输出为命令自身输出与退出状态。 |

Python 入口使用项目 `.venv-cpu` 或 `.venv-gpu`，缓存位于项目内。具体执行结果见 PROGRESS 和 S0 操作文档。代理包装仅适用于rc中独立定义的`proxy_on()`；匹配不到明确失败，改在用户终端手动启用，不执行其他初始化。
