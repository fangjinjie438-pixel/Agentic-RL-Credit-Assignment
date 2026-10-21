# S0 metadata and CPU import probe

Result: **failed**; interpreter: `/home/fangjinjie/project/credit_assign/.venv-gpu/bin/python`.

CUDA devices were hidden. These results do not validate GPU compatibility, BF16 hardware, inference, P2P, NCCL, or training.

| Probe | Result | Exit code | Seconds |
| --- | --- | --- | --- |
| metadata | passed | 0 | 0.174 |
| torch | passed | 0 | 3.853 |
| torchvision | passed | 0 | 6.429 |
| torchaudio | passed | 0 | 4.258 |
| xformers_ops | failed | 1 | 8.272 |
| torch_fsdp2 | passed | 0 | 6.229 |
| transformers | passed | 0 | 7.806 |
| qwen3_config | passed | 0 | 5.545 |
| qwen3_model | passed | 0 | 9.826 |
| peft | passed | 0 | 11.223 |
| accelerate | passed | 0 | 4.066 |
| torchdata | passed | 0 | 3.563 |
| ray | passed | 0 | 0.832 |
| tensordict | passed | 0 | 6.414 |
| vllm | passed | 0 | 14.87 |
| verl | passed | 0 | 8.774 |
| verl_main_ppo | passed | 0 | 16.873 |
| verl_core_algos | passed | 0 | 10.662 |
| verl_fsdp_utils | passed | 0 | 10.282 |
| verl_fsdp_worker | passed | 0 | 10.778 |
| verl_vllm_rollout | passed | 0 | 16.97 |
| verl_vllm_async_server | failed | 1 | 18.763 |
| verl_agent_loop | passed | 0 | 13.113 |
| verl_tool_agent_loop | passed | 0 | 12.468 |

Full commands, structured per-import results, stdout, stderr and metadata are retained in `report.json`.
