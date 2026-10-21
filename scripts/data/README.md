# S2 数据来源工具

`fetch_amazon_pilot.py` 只在人工选择来源时用 HTTP Range 从固定 HF revision 的 Electronics Parquet 首个 row group 抽取元数据。输入固定公开 URL、新输出目录；输出网络请求/字节/哈希清单与原始 JSON 元数据，不生成训练任务，不加载模型或访问教师 API。运行时隐藏 GPU，仅导入项目已装 PyArrow 和标准库。

```bash
CUDA_VISIBLE_DEVICES='' .venv-cpu/bin/python scripts/with_proxy.py -- .venv-gpu/bin/python scripts/data/fetch_amazon_pilot.py --output logs/my-s2-source
```

实际验证状态与来源边界见 `docs/s2-source-audit.md`。输出目录须不存在；失败保留现有证据、换新目录恢复。固定版本下载失败时不自动更换数据源或 revision；无需 GPU、系统 Toolkit 或 checkpoint。普通离线 S2 流水线不依赖 PyArrow。
