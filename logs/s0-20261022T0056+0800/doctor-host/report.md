# S0 read-only environment report

Collected (UTC): 2026-10-21T16:56:51.992309+00:00
Project: `/home/fangjinjie/project/credit_assign`

GPU allocation: **not confirmed**. Real GPU computation: **pending**.
The candidate verl 0.6.1 + vLLM 0.10.0/cu126 + PyTorch 2.7.1/cu126 stack is **not validated**.
nvidia-smi CUDA Version is a driver capability. Toolkit paths are metadata only; no Toolkit executable was invoked and Toolkit versions remain unverified.
PIX and P2P capability matrices describe topology/capability only; no GPU transfer or NCCL operation was executed.

## Python and dependencies

Python: `3.11.16`; executable: `/home/fangjinjie/project/credit_assign/.venv-cpu/bin/python`; target: 3.11.

| Distribution | Installed | Candidate | Version comparison |
| --- | --- | --- | --- |
| torch | not_installed | 2.7.1 | missing |
| verl | not_installed | 0.6.1 | missing |
| vllm | not_installed | 0.10.0 | missing |
| transformers | not_installed | 4.53.2 | missing |
| ray | not_installed | not pinned | missing |
| peft | not_installed | not pinned | missing |
| flash-attn | not_installed | not pinned | missing |
| accelerate | not_installed | not pinned | missing |
| numpy | not_installed | not pinned | missing |
| nvidia-nccl-cu12 | not_installed | not pinned | missing |
| nvidia-cuda-runtime-cu12 | not_installed | not pinned | missing |

## Host, CPU, memory and filesystems

```json
{
  "hostname": "A6000",
  "os": "Linux-6.8.0-90-generic-x86_64-with-glibc2.35",
  "libc": {
    "implementation": "glibc",
    "version": "2.35"
  },
  "os_release": {
    "NAME": "Ubuntu",
    "ID": "ubuntu",
    "PRETTY_NAME": "Ubuntu 22.04.5 LTS",
    "VERSION_ID": "22.04",
    "VERSION": "22.04.5 LTS (Jammy Jellyfish)",
    "VERSION_CODENAME": "jammy",
    "ID_LIKE": "debian",
    "HOME_URL": "https://www.ubuntu.com/",
    "SUPPORT_URL": "https://help.ubuntu.com/",
    "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
    "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
    "UBUNTU_CODENAME": "jammy"
  },
  "cpu": {
    "logical_cpu_count": 48,
    "machine": "x86_64",
    "model_names": [
      "Intel(R) Xeon(R) Silver 4214 CPU @ 2.20GHz"
    ],
    "physical_socket_count": 2,
    "process_affinity_cpu_count": 48
  },
  "memory": {
    "status": "observed",
    "bytes": {
      "MemTotal": 539610329088,
      "MemAvailable": 420187529216,
      "SwapTotal": 17179865088,
      "SwapFree": 11449163776
    }
  },
  "filesystems": [
    {
      "path": "/home/fangjinjie/project/credit_assign",
      "status": "observed",
      "total_bytes": 47809250451456,
      "used_bytes": 43642374770688,
      "free_bytes": 2006809870336,
      "used_percent": 91.28
    },
    {
      "path": "/tmp",
      "status": "observed",
      "total_bytes": 233581228032,
      "used_bytes": 187291377664,
      "free_bytes": 34350030848,
      "used_percent": 80.18
    },
    {
      "path": "/dev/shm",
      "status": "observed",
      "total_bytes": 269805162496,
      "used_bytes": 149450752,
      "free_bytes": 269655711744,
      "used_percent": 0.06
    }
  ]
}
```

## Project top-level state

```json
{
  "path": "/home/fangjinjie/project/credit_assign",
  "inspection_depth": 1,
  "hidden_entries_omitted": 5,
  "top_level_entries": [
    {
      "name": "AGENTS.md",
      "type": "file"
    },
    {
      "name": "PLAN.md",
      "type": "file"
    },
    {
      "name": "PROGRESS.md",
      "type": "file"
    },
    {
      "name": "README.md",
      "type": "file"
    },
    {
      "name": "configs",
      "type": "directory"
    },
    {
      "name": "docs",
      "type": "directory"
    },
    {
      "name": "logs",
      "type": "directory"
    },
    {
      "name": "pyproject.toml",
      "type": "file"
    },
    {
      "name": "requirements",
      "type": "directory"
    },
    {
      "name": "src",
      "type": "directory"
    },
    {
      "name": "tests",
      "type": "directory"
    }
  ],
  "git_directory_present": false,
  "git_note": "Directory presence is metadata only; consult git command results to establish repository validity.",
  "status": "observed"
}
```

## Toolkit metadata (no Toolkit execution)

```json
{
  "status": "metadata_only",
  "execution_policy": "no_toolkit_execution",
  "installed_versions": "not_verified_no_toolkit_execution",
  "installations": [
    {
      "path": "/usr/local/cuda",
      "is_symlink": true,
      "resolved_path": "/usr/local/cuda-11.3",
      "is_directory": true,
      "nvcc_path_exists": true,
      "symlink_target": "/usr/local/cuda-11.3/"
    },
    {
      "path": "/usr/local/cuda-10.2",
      "is_symlink": false,
      "resolved_path": "/usr/local/cuda-10.2",
      "is_directory": true,
      "nvcc_path_exists": true
    },
    {
      "path": "/usr/local/cuda-11.3",
      "is_symlink": false,
      "resolved_path": "/usr/local/cuda-11.3",
      "is_directory": true,
      "nvcc_path_exists": true
    },
    {
      "path": "/usr/local/cuda-11.7",
      "is_symlink": false,
      "resolved_path": "/usr/local/cuda-11.7",
      "is_directory": true,
      "nvcc_path_exists": true
    }
  ],
  "nvcc_on_path": null
}
```

## Allocation hints (not authorization)

```json
{
  "status": "not_confirmed",
  "environment_hints": {},
  "note": "Environment hints and free memory do not authorize GPU use. Confirm assigned GPU UUIDs externally before computing."
}
```

## GPU inventory and processes

```json
{
  "inventory": {
    "status": "observed",
    "rows": [
      {
        "index": "0",
        "uuid": "GPU-3032353e-1a50-d282-c97a-9359dd81765f",
        "name": "NVIDIA GeForce RTX 3090",
        "memory.total": "24576",
        "memory.used": "16065",
        "memory.free": "8091",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:1B:00.0"
      },
      {
        "index": "1",
        "uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "name": "NVIDIA RTX A6000",
        "memory.total": "49140",
        "memory.used": "11489",
        "memory.free": "37081",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:1C:00.0"
      },
      {
        "index": "2",
        "uuid": "GPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a",
        "name": "NVIDIA GeForce RTX 3090",
        "memory.total": "24576",
        "memory.used": "7225",
        "memory.free": "16930",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:1D:00.0"
      },
      {
        "index": "3",
        "uuid": "GPU-c8e79920-bd45-2d86-d5d4-1b622bb89872",
        "name": "NVIDIA GeForce RTX 3090",
        "memory.total": "24576",
        "memory.used": "4336",
        "memory.free": "19819",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:1E:00.0"
      },
      {
        "index": "4",
        "uuid": "GPU-f772dd3f-e279-8cdc-62dd-7b39740b2063",
        "name": "NVIDIA RTX A6000",
        "memory.total": "49140",
        "memory.used": "42961",
        "memory.free": "5610",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:3E:00.0"
      },
      {
        "index": "5",
        "uuid": "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af",
        "name": "NVIDIA RTX A6000",
        "memory.total": "49140",
        "memory.used": "9019",
        "memory.free": "39552",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:3F:00.0"
      },
      {
        "index": "6",
        "uuid": "GPU-16662740-b048-cf14-153f-715029deba47",
        "name": "NVIDIA GeForce RTX 3090",
        "memory.total": "24576",
        "memory.used": "15",
        "memory.free": "24140",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:40:00.0"
      },
      {
        "index": "7",
        "uuid": "GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03",
        "name": "NVIDIA RTX A6000",
        "memory.total": "49140",
        "memory.used": "3703",
        "memory.free": "44868",
        "driver_version": "560.35.03",
        "pci.bus_id": "00000000:41:00.0"
      }
    ],
    "malformed_rows": []
  },
  "compute_processes": {
    "status": "observed",
    "rows": [
      {
        "gpu_uuid": "GPU-3032353e-1a50-d282-c97a-9359dd81765f",
        "pid": "2924522",
        "process_name": "/home/zhengyingxiong/conda/ENTER/bin/python3",
        "used_gpu_memory": "10332"
      },
      {
        "gpu_uuid": "GPU-3032353e-1a50-d282-c97a-9359dd81765f",
        "pid": "3443555",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1784"
      },
      {
        "gpu_uuid": "GPU-3032353e-1a50-d282-c97a-9359dd81765f",
        "pid": "3445326",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1786"
      },
      {
        "gpu_uuid": "GPU-3032353e-1a50-d282-c97a-9359dd81765f",
        "pid": "3445777",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1860"
      },
      {
        "gpu_uuid": "GPU-3032353e-1a50-d282-c97a-9359dd81765f",
        "pid": "3446413",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "256"
      },
      {
        "gpu_uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "pid": "3437412",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1796"
      },
      {
        "gpu_uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "pid": "3438412",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1868"
      },
      {
        "gpu_uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "pid": "3438789",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1868"
      },
      {
        "gpu_uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "pid": "3442325",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1840"
      },
      {
        "gpu_uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "pid": "3444820",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1796"
      },
      {
        "gpu_uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "pid": "3445581",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1796"
      },
      {
        "gpu_uuid": "GPU-595536f6-a9e7-a60d-ab7e-c0341726e449",
        "pid": "3446043",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "686"
      },
      {
        "gpu_uuid": "GPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a",
        "pid": "3442692",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1832"
      },
      {
        "gpu_uuid": "GPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a",
        "pid": "3443556",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1784"
      },
      {
        "gpu_uuid": "GPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a",
        "pid": "3443973",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1784"
      },
      {
        "gpu_uuid": "GPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a",
        "pid": "3444528",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1786"
      },
      {
        "gpu_uuid": "GPU-c8e79920-bd45-2d86-d5d4-1b622bb89872",
        "pid": "3442965",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1832"
      },
      {
        "gpu_uuid": "GPU-c8e79920-bd45-2d86-d5d4-1b622bb89872",
        "pid": "3444821",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1786"
      },
      {
        "gpu_uuid": "GPU-c8e79920-bd45-2d86-d5d4-1b622bb89872",
        "pid": "3446044",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "684"
      },
      {
        "gpu_uuid": "GPU-f772dd3f-e279-8cdc-62dd-7b39740b2063",
        "pid": "446549",
        "process_name": "/home/zhengyingxiong/conda/ENTER/bin/python3",
        "used_gpu_memory": "10460"
      },
      {
        "gpu_uuid": "GPU-f772dd3f-e279-8cdc-62dd-7b39740b2063",
        "pid": "2456287",
        "process_name": "/home/zhengyingxiong/conda/ENTER/bin/python3",
        "used_gpu_memory": "32466"
      },
      {
        "gpu_uuid": "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af",
        "pid": "3443304",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1794"
      },
      {
        "gpu_uuid": "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af",
        "pid": "3443557",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1794"
      },
      {
        "gpu_uuid": "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af",
        "pid": "3444260",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1794"
      },
      {
        "gpu_uuid": "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af",
        "pid": "3444822",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1796"
      },
      {
        "gpu_uuid": "GPU-2e81c395-ac38-bfde-adba-34f3d967f7af",
        "pid": "3445106",
        "process_name": "/home/wangcheng/project/RNA/ReGRA/.venv/bin/python",
        "used_gpu_memory": "1796"
      },
      {
        "gpu_uuid": "GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03",
        "pid": "1939306",
        "process_name": "python3",
        "used_gpu_memory": "2024"
      },
      {
        "gpu_uuid": "GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03",
        "pid": "3180510",
        "process_name": "python3",
        "used_gpu_memory": "1648"
      }
    ],
    "malformed_rows": []
  },
  "memory_unit": "MiB (nvidia-smi CSV without unit labels)",
  "topology_note": "PIX is a PCIe switch path, not NVLink or proof of working P2P. Capability queries are not transfer tests.",
  "cuda_version_note": "nvidia-smi CUDA Version is driver capability, not installed Toolkit or PyTorch CUDA runtime.",
  "torch_cuda_runtime": "not_verified_no_torch_import",
  "nccl_runtime": "not_verified_no_gpu_execution"
}
```

## Validation status

```json
{
  "read_only_inventory": "collected_with_per_probe_status",
  "gpu_allocation": "pending",
  "dependency_installation": "pending",
  "candidate_stack_compatibility": "pending",
  "real_gpu_execution": "pending",
  "p2p_transfer": "pending",
  "nccl_collective": "pending",
  "torch_cuda_runtime": "pending",
  "multi_turn_lora_sync": "pending"
}
```

## Command evidence

### nvidia_smi

```json
{
  "argv": [
    "nvidia-smi"
  ],
  "timeout_seconds": 10.0,
  "returncode": 0,
  "stdout": "Thu Oct 22 00:56:48 2026       \n+-----------------------------------------------------------------------------------------+\n| NVIDIA-SMI 560.35.03              Driver Version: 560.35.03      CUDA Version: 12.6     |\n|-----------------------------------------+------------------------+----------------------+\n| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |\n| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |\n|                                         |                        |               MIG M. |\n|=========================================+========================+======================|\n|   0  NVIDIA GeForce RTX 3090        Off |   00000000:1B:00.0 Off |                  N/A |\n|100%   87C    P0            293W /  350W |   16065MiB /  24576MiB |     99%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n|   1  NVIDIA RTX A6000               Off |   00000000:1C:00.0 Off |                  Off |\n| 62%   84C    P0            262W /  300W |   11281MiB /  49140MiB |    100%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n|   2  NVIDIA GeForce RTX 3090        Off |   00000000:1D:00.0 Off |                  N/A |\n|100%   80C    P0            332W /  350W |    7225MiB /  24576MiB |    100%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n|   3  NVIDIA GeForce RTX 3090        Off |   00000000:1E:00.0 Off |                  N/A |\n| 98%   74C    P0            308W /  350W |    4334MiB /  24576MiB |     85%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n|   4  NVIDIA RTX A6000               Off |   00000000:3E:00.0 Off |                  Off |\n| 66%   85C    P0            288W /  300W |   42961MiB /  49140MiB |    100%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n|   5  NVIDIA RTX A6000               Off |   00000000:3F:00.0 Off |                  Off |\n| 56%   80C    P0            279W /  300W |    9019MiB /  49140MiB |     98%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n|   6  NVIDIA GeForce RTX 3090        Off |   00000000:40:00.0 Off |                  N/A |\n| 41%   44C    P8             28W /  350W |      15MiB /  24576MiB |      0%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n|   7  NVIDIA RTX A6000               Off |   00000000:41:00.0 Off |                  Off |\n| 56%   80C    P0            153W /  300W |    3703MiB /  49140MiB |     79%      Default |\n|                                         |                        |                  N/A |\n+-----------------------------------------+------------------------+----------------------+\n                                                                                         \n+-----------------------------------------------------------------------------------------+\n| Processes:                                                                              |\n|  GPU   GI   CI        PID   Type   Process name                              GPU Memory |\n|        ID   ID                                                               Usage      |\n|=========================================================================================|\n|    0   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    0   N/A  N/A   2924522      C   ...ngyingxiong/conda/ENTER/bin/python3      10332MiB |\n|    0   N/A  N/A   3443555      C   .../project/RNA/ReGRA/.venv/bin/python       1784MiB |\n|    0   N/A  N/A   3445326      C   .../project/RNA/ReGRA/.venv/bin/python       1786MiB |\n|    0   N/A  N/A   3445777      C   .../project/RNA/ReGRA/.venv/bin/python       1860MiB |\n|    0   N/A  N/A   3446413      C   .../project/RNA/ReGRA/.venv/bin/python        256MiB |\n|    1   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    1   N/A  N/A   3437412      C   .../project/RNA/ReGRA/.venv/bin/python       1796MiB |\n|    1   N/A  N/A   3438412      C   .../project/RNA/ReGRA/.venv/bin/python       1868MiB |\n|    1   N/A  N/A   3438789      C   .../project/RNA/ReGRA/.venv/bin/python       1868MiB |\n|    1   N/A  N/A   3442325      C   .../project/RNA/ReGRA/.venv/bin/python       1840MiB |\n|    1   N/A  N/A   3444820      C   .../project/RNA/ReGRA/.venv/bin/python       1796MiB |\n|    1   N/A  N/A   3445581      C   .../project/RNA/ReGRA/.venv/bin/python       1796MiB |\n|    1   N/A  N/A   3446043      C   .../project/RNA/ReGRA/.venv/bin/python        262MiB |\n|    2   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    2   N/A  N/A   3442692      C   .../project/RNA/ReGRA/.venv/bin/python       1832MiB |\n|    2   N/A  N/A   3443556      C   .../project/RNA/ReGRA/.venv/bin/python       1784MiB |\n|    2   N/A  N/A   3443973      C   .../project/RNA/ReGRA/.venv/bin/python       1784MiB |\n|    2   N/A  N/A   3444528      C   .../project/RNA/ReGRA/.venv/bin/python       1786MiB |\n|    3   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    3   N/A  N/A   3442965      C   .../project/RNA/ReGRA/.venv/bin/python       1832MiB |\n|    3   N/A  N/A   3444821      C   .../project/RNA/ReGRA/.venv/bin/python       1786MiB |\n|    3   N/A  N/A   3446044      C   .../project/RNA/ReGRA/.venv/bin/python        682MiB |\n|    4   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    4   N/A  N/A    446549      C   ...ngyingxiong/conda/ENTER/bin/python3      10460MiB |\n|    4   N/A  N/A   2456287      C   ...ngyingxiong/conda/ENTER/bin/python3      32466MiB |\n|    5   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    5   N/A  N/A   3443304      C   .../project/RNA/ReGRA/.venv/bin/python       1794MiB |\n|    5   N/A  N/A   3443557      C   .../project/RNA/ReGRA/.venv/bin/python       1794MiB |\n|    5   N/A  N/A   3444260      C   .../project/RNA/ReGRA/.venv/bin/python       1794MiB |\n|    5   N/A  N/A   3444822      C   .../project/RNA/ReGRA/.venv/bin/python       1796MiB |\n|    5   N/A  N/A   3445106      C   .../project/RNA/ReGRA/.venv/bin/python       1796MiB |\n|    6   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    7   N/A  N/A      4106      G   /usr/lib/xorg/Xorg                              4MiB |\n|    7   N/A  N/A   1939306      C   python3                                      2024MiB |\n|    7   N/A  N/A   3180510      C   python3                                      1648MiB |\n+-----------------------------------------------------------------------------------------+\n",
  "stderr": "",
  "status": "ok",
  "elapsed_seconds": 1.293
}
```

### gpu_inventory

```json
{
  "argv": [
    "nvidia-smi",
    "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,driver_version,pci.bus_id",
    "--format=csv,noheader,nounits"
  ],
  "timeout_seconds": 10.0,
  "returncode": 0,
  "stdout": "0, GPU-3032353e-1a50-d282-c97a-9359dd81765f, NVIDIA GeForce RTX 3090, 24576, 16065, 8091, 560.35.03, 00000000:1B:00.0\n1, GPU-595536f6-a9e7-a60d-ab7e-c0341726e449, NVIDIA RTX A6000, 49140, 11489, 37081, 560.35.03, 00000000:1C:00.0\n2, GPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a, NVIDIA GeForce RTX 3090, 24576, 7225, 16930, 560.35.03, 00000000:1D:00.0\n3, GPU-c8e79920-bd45-2d86-d5d4-1b622bb89872, NVIDIA GeForce RTX 3090, 24576, 4336, 19819, 560.35.03, 00000000:1E:00.0\n4, GPU-f772dd3f-e279-8cdc-62dd-7b39740b2063, NVIDIA RTX A6000, 49140, 42961, 5610, 560.35.03, 00000000:3E:00.0\n5, GPU-2e81c395-ac38-bfde-adba-34f3d967f7af, NVIDIA RTX A6000, 49140, 9019, 39552, 560.35.03, 00000000:3F:00.0\n6, GPU-16662740-b048-cf14-153f-715029deba47, NVIDIA GeForce RTX 3090, 24576, 15, 24140, 560.35.03, 00000000:40:00.0\n7, GPU-4c457a8a-39a3-5346-1f3c-5993b3102d03, NVIDIA RTX A6000, 49140, 3703, 44868, 560.35.03, 00000000:41:00.0\n",
  "stderr": "",
  "status": "ok",
  "elapsed_seconds": 0.289
}
```

### gpu_processes

```json
{
  "argv": [
    "nvidia-smi",
    "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory",
    "--format=csv,noheader,nounits"
  ],
  "timeout_seconds": 10.0,
  "returncode": 0,
  "stdout": "GPU-3032353e-1a50-d282-c97a-9359dd81765f, 2924522, /home/zhengyingxiong/conda/ENTER/bin/python3, 10332\nGPU-3032353e-1a50-d282-c97a-9359dd81765f, 3443555, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1784\nGPU-3032353e-1a50-d282-c97a-9359dd81765f, 3445326, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1786\nGPU-3032353e-1a50-d282-c97a-9359dd81765f, 3445777, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1860\nGPU-3032353e-1a50-d282-c97a-9359dd81765f, 3446413, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 256\nGPU-595536f6-a9e7-a60d-ab7e-c0341726e449, 3437412, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1796\nGPU-595536f6-a9e7-a60d-ab7e-c0341726e449, 3438412, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1868\nGPU-595536f6-a9e7-a60d-ab7e-c0341726e449, 3438789, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1868\nGPU-595536f6-a9e7-a60d-ab7e-c0341726e449, 3442325, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1840\nGPU-595536f6-a9e7-a60d-ab7e-c0341726e449, 3444820, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1796\nGPU-595536f6-a9e7-a60d-ab7e-c0341726e449, 3445581, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1796\nGPU-595536f6-a9e7-a60d-ab7e-c0341726e449, 3446043, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 686\nGPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a, 3442692, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1832\nGPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a, 3443556, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1784\nGPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a, 3443973, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1784\nGPU-9fc58bf8-5c1d-170d-d506-ff01af38be1a, 3444528, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1786\nGPU-c8e79920-bd45-2d86-d5d4-1b622bb89872, 3442965, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1832\nGPU-c8e79920-bd45-2d86-d5d4-1b622bb89872, 3444821, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1786\nGPU-c8e79920-bd45-2d86-d5d4-1b622bb89872, 3446044, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 684\nGPU-f772dd3f-e279-8cdc-62dd-7b39740b2063, 446549, /home/zhengyingxiong/conda/ENTER/bin/python3, 10460\nGPU-f772dd3f-e279-8cdc-62dd-7b39740b2063, 2456287, /home/zhengyingxiong/conda/ENTER/bin/python3, 32466\nGPU-2e81c395-ac38-bfde-adba-34f3d967f7af, 3443304, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1794\nGPU-2e81c395-ac38-bfde-adba-34f3d967f7af, 3443557, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1794\nGPU-2e81c395-ac38-bfde-adba-34f3d967f7af, 3444260, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1794\nGPU-2e81c395-ac38-bfde-adba-34f3d967f7af, 3444822, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1796\nGPU-2e81c395-ac38-bfde-adba-34f3d967f7af, 3445106, /home/wangcheng/project/RNA/ReGRA/.venv/bin/python, 1796\nGPU-4c457a8a-39a3-5346-1f3c-5993b3102d03, 1939306, python3, 2024\nGPU-4c457a8a-39a3-5346-1f3c-5993b3102d03, 3180510, python3, 1648\n",
  "stderr": "",
  "status": "ok",
  "elapsed_seconds": 0.155
}
```

### gpu_topology

```json
{
  "argv": [
    "nvidia-smi",
    "topo",
    "-m"
  ],
  "timeout_seconds": 10.0,
  "returncode": 0,
  "stdout": "\t\u001b[4mGPU0\tGPU1\tGPU2\tGPU3\tGPU4\tGPU5\tGPU6\tGPU7\tCPU Affinity\tNUMA Affinity\tGPU NUMA ID\u001b[0m\nGPU0\t X \tPIX\tPIX\tPIX\tNODE\tNODE\tNODE\tNODE\t0-11,24-35\t0\t\tN/A\nGPU1\tPIX\t X \tPIX\tPIX\tNODE\tNODE\tNODE\tNODE\t0-11,24-35\t0\t\tN/A\nGPU2\tPIX\tPIX\t X \tPIX\tNODE\tNODE\tNODE\tNODE\t0-11,24-35\t0\t\tN/A\nGPU3\tPIX\tPIX\tPIX\t X \tNODE\tNODE\tNODE\tNODE\t0-11,24-35\t0\t\tN/A\nGPU4\tNODE\tNODE\tNODE\tNODE\t X \tPIX\tPIX\tPIX\t0-11,24-35\t0\t\tN/A\nGPU5\tNODE\tNODE\tNODE\tNODE\tPIX\t X \tPIX\tPIX\t0-11,24-35\t0\t\tN/A\nGPU6\tNODE\tNODE\tNODE\tNODE\tPIX\tPIX\t X \tPIX\t0-11,24-35\t0\t\tN/A\nGPU7\tNODE\tNODE\tNODE\tNODE\tPIX\tPIX\tPIX\t X \t0-11,24-35\t0\t\tN/A\n\nLegend:\n\n  X    = Self\n  SYS  = Connection traversing PCIe as well as the SMP interconnect between NUMA nodes (e.g., QPI/UPI)\n  NODE = Connection traversing PCIe as well as the interconnect between PCIe Host Bridges within a NUMA node\n  PHB  = Connection traversing PCIe as well as a PCIe Host Bridge (typically the CPU)\n  PXB  = Connection traversing multiple PCIe bridges (without traversing the PCIe Host Bridge)\n  PIX  = Connection traversing at most a single PCIe bridge\n  NV#  = Connection traversing a bonded set of # NVLinks\n",
  "stderr": "",
  "status": "ok",
  "elapsed_seconds": 1.807
}
```

### p2p_read_capability

```json
{
  "argv": [
    "nvidia-smi",
    "topo",
    "-p2p",
    "r"
  ],
  "timeout_seconds": 10.0,
  "returncode": 0,
  "stdout": " \t\u001b[4mGPU0\tGPU1\tGPU2\tGPU3\tGPU4\tGPU5\tGPU6\tGPU7\t\u001b[0m\n GPU0\tX\tCNS\tCNS\tCNS\tCNS\tCNS\tCNS\tCNS\t\n GPU1\tCNS\tX\tCNS\tCNS\tOK\tOK\tCNS\tOK\t\n GPU2\tCNS\tCNS\tX\tCNS\tCNS\tCNS\tCNS\tCNS\t\n GPU3\tCNS\tCNS\tCNS\tX\tCNS\tCNS\tCNS\tCNS\t\n GPU4\tCNS\tOK\tCNS\tCNS\tX\tOK\tCNS\tOK\t\n GPU5\tCNS\tOK\tCNS\tCNS\tOK\tX\tCNS\tOK\t\n GPU6\tCNS\tCNS\tCNS\tCNS\tCNS\tCNS\tX\tCNS\t\n GPU7\tCNS\tOK\tCNS\tCNS\tOK\tOK\tCNS\tX\t\n\nLegend:\n\n  X    = Self\n  OK   = Status Ok\n  CNS  = Chipset not supported\n  GNS  = GPU not supported\n  TNS  = Topology not supported\n  NS   = Not supported\n  U    = Unknown\n",
  "stderr": "",
  "status": "ok",
  "elapsed_seconds": 0.129
}
```

### p2p_write_capability

```json
{
  "argv": [
    "nvidia-smi",
    "topo",
    "-p2p",
    "w"
  ],
  "timeout_seconds": 10.0,
  "returncode": 0,
  "stdout": " \t\u001b[4mGPU0\tGPU1\tGPU2\tGPU3\tGPU4\tGPU5\tGPU6\tGPU7\t\u001b[0m\n GPU0\tX\tCNS\tCNS\tCNS\tCNS\tCNS\tCNS\tCNS\t\n GPU1\tCNS\tX\tCNS\tCNS\tOK\tOK\tCNS\tOK\t\n GPU2\tCNS\tCNS\tX\tCNS\tCNS\tCNS\tCNS\tCNS\t\n GPU3\tCNS\tCNS\tCNS\tX\tCNS\tCNS\tCNS\tCNS\t\n GPU4\tCNS\tOK\tCNS\tCNS\tX\tOK\tCNS\tOK\t\n GPU5\tCNS\tOK\tCNS\tCNS\tOK\tX\tCNS\tOK\t\n GPU6\tCNS\tCNS\tCNS\tCNS\tCNS\tCNS\tX\tCNS\t\n GPU7\tCNS\tOK\tCNS\tCNS\tOK\tOK\tCNS\tX\t\n\nLegend:\n\n  X    = Self\n  OK   = Status Ok\n  CNS  = Chipset not supported\n  GNS  = GPU not supported\n  TNS  = Topology not supported\n  NS   = Not supported\n  U    = Unknown\n",
  "stderr": "",
  "status": "ok",
  "elapsed_seconds": 0.119
}
```

### git_revision

```json
{
  "argv": [
    "git",
    "--no-optional-locks",
    "-C",
    "/home/fangjinjie/project/credit_assign",
    "rev-parse",
    "HEAD"
  ],
  "timeout_seconds": 10.0,
  "returncode": 128,
  "stdout": "",
  "stderr": "fatal: not a git repository (or any parent up to mount point /)\nStopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set).\n",
  "status": "failed",
  "elapsed_seconds": 0.003
}
```

### git_status

```json
{
  "argv": [
    "git",
    "--no-optional-locks",
    "-C",
    "/home/fangjinjie/project/credit_assign",
    "status",
    "--short",
    "--untracked-files=no"
  ],
  "timeout_seconds": 10.0,
  "returncode": 128,
  "stdout": "",
  "stderr": "fatal: not a git repository (or any parent up to mount point /)\nStopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set).\n",
  "status": "failed",
  "elapsed_seconds": 0.003
}
```

