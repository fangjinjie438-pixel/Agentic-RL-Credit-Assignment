# S0 metadata and CPU import probe

Result: **failed**; interpreter: `/home/fangjinjie/project/credit_assign/.venv-gpu/bin/python`.

CUDA devices were hidden. These results do not validate GPU compatibility, BF16 hardware, inference, P2P, NCCL, or training.

| Probe | Result | Exit code | Seconds |
| --- | --- | --- | --- |
| metadata | passed | 0 | 0.183 |
| torch | passed | 0 | 17.115 |
| torchvision | passed | 0 | 15.059 |
| torchaudio | passed | 0 | 4.483 |
| xformers_ops | failed | 1 | 4.137 |
| torch_fsdp2 | passed | 0 | 7.119 |
| transformers | passed | 0 | 11.705 |
| qwen3_config | passed | 0 | 7.011 |
| qwen3_model | failed | 1 | 8.864 |
| peft | failed | 1 | 8.989 |
| accelerate | passed | 0 | 3.655 |
| torchdata | passed | 0 | 3.713 |
| ray | passed | 0 | 1.92 |
| tensordict | passed | 0 | 6.443 |
| vllm | failed | 1 | 8.43 |
| verl | passed | 0 | 7.762 |
| verl_main_ppo | failed | 1 | 7.683 |
| verl_core_algos | failed | 1 | 8.032 |
| verl_fsdp_utils | failed | 1 | 9.436 |
| verl_fsdp_worker | failed | 1 | 9.42 |
| verl_vllm_rollout | failed | 1 | 7.743 |
| verl_vllm_async_server | failed | 1 | 8.81 |
| verl_agent_loop | failed | 1 | 8.035 |
| verl_tool_agent_loop | failed | 1 | 7.783 |

Full commands, structured per-import results, stdout, stderr and metadata are retained in `report.json`.
