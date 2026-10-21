# 项目独立编译器入口（S0）

| 文件 | 用途、调用与执行方式 |
| --- | --- |
| `cc` | POSIX shell 入口，定位项目根，调用 `.venv-toolchain/bin/python -m ziglang cc`，透传 clang 风格参数，生成调用者指定目标；Triton通过CC调用。例：`scripts/toolchain/cc --version`。 |
| `cxx` | 同样调用项目 `.venv-toolchain` 中的 `ziglang c++`，供CXX使用。例：`scripts/toolchain/cxx --version`。未验证前不称完整Torch Inductor C++支持。 |

依赖候选在 `requirements/toolchain-candidate.in`，编译器安装在专属 `.venv-toolchain`，不改变CPU零依赖环境或GPU模型依赖。Zig 是独立编译器，Python和编译程序都在项目环境；不调用系统GCC/nvcc。两个包装器只设置项目Zig缓存、转发参数，没有GPU计算。系统NVIDIA驱动库是运行GPU的必要基础，与系统开发Toolkit分开；需要时项目 `.tools/cuda-driver/lib` 仅链接已存在的驱动库，不修改系统库。

验证状态看 PROGRESS；包装器存在不代表编译测试通过。缺少ziglang时返回导入错误，不回落系统工具；重建环境后按锁定版本重装，再运行S0编译验收。
