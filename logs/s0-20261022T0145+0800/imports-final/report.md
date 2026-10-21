# S0 metadata and CPU import probe

Result: **passed**; interpreter: `/home/fangjinjie/project/credit_assign/.venv-gpu/bin/python`.

CUDA devices were hidden. These results do not validate GPU compatibility, BF16 hardware, inference, P2P, NCCL, or training.

| Probe | Result | Exit code | Seconds |
| --- | --- | --- | --- |
| metadata | passed | 0 | 0.174 |
| torch | passed | 0 | 3.422 |
| torchvision | passed | 0 | 6.542 |
| torchaudio | passed | 0 | 4.016 |
| xformers_ops | passed | 0 | 7.465 |
| flash_attn | passed | 0 | 3.739 |
| torch_fsdp2 | passed | 0 | 6.019 |
| transformers | passed | 0 | 8.482 |
| qwen3_config | passed | 0 | 6.125 |
| qwen3_model | passed | 0 | 8.997 |
| peft | passed | 0 | 10.511 |
| accelerate | passed | 0 | 4.893 |
| torchdata | passed | 0 | 4.107 |
| ray | passed | 0 | 0.934 |
| tensordict | passed | 0 | 6.362 |
| vllm | passed | 0 | 11.719 |
| verl | passed | 0 | 7.147 |
| verl_main_ppo | passed | 0 | 12.336 |
| verl_core_algos | passed | 0 | 10.916 |
| verl_fsdp_utils | passed | 0 | 10.377 |
| verl_fsdp_worker | passed | 0 | 11.064 |
| verl_vllm_rollout | passed | 0 | 16.367 |
| verl_vllm_async_server | passed | 0 | 18.1 |
| verl_agent_loop | passed | 0 | 12.892 |
| verl_tool_agent_loop | passed | 0 | 13.121 |

Full commands, structured per-import results, stdout, stderr and metadata are retained in `report.json`.
