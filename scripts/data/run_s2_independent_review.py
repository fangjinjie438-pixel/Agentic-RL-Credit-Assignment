"""Run a bounded real Qwen3-8B S2 semantic pilot on one allocated GPU.

Inputs are a verified dataset, fixed local official model and its verified-file
report, plus an explicit allocation file/UUID. Outputs preserve complete prompts,
raw generated tokens/text, strict decisions and command/model/GPU/hash evidence.
Only train/dev is loaded. This is model review, never human approval or training.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from procure_rl.data.independent import (PROMPT_VERSION, make_independent_prompt,
                                         parse_independent_response)
from procure_rl.data.pipeline import load_dataset
from procure_rl.data.review_material import independent_review_inputs, prepare_review_material
from procure_rl.env.catalog import digest
from procure_rl.runtime import RunRecord, sha256_file, timestamp

MODEL = "Qwen/Qwen3-8B"


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stream_sha256(path: Path) -> str:
    """Hash multi-GB weights with an 8MiB CPU memory bound."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while data := handle.read(8 * 1024 * 1024):
            hasher.update(data)
    return hasher.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--allocation", type=Path, required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=7)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-context-tokens", type=int, default=16384)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--prepare-only", action="store_true",
                      help="Hide all GPUs and render/tokenize private prompts without loading model weights")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    run = RunRecord(args.output, root, [sys.executable, *sys.argv],
                    execution_kind="cpu_tokenizer_prompt_preflight" if args.prepare_only else
                    "allocated_gpu_independent_semantic_review", stage="S2")
    artifacts = {}
    try:
        if (Path(sys.prefix).absolute() != root / ".venv-gpu" or
                not Path(sys.base_prefix).resolve().is_relative_to((root / ".tools/python").resolve())):
            raise ValueError("Project .venv-gpu and independent base interpreter required")
        if not 1 <= args.limit <= 7 or not 1 <= args.max_new_tokens <= 1024 or not 1024 <= args.max_context_tokens <= 16384:
            raise ValueError("This S2 pilot is limited to seven tasks/16K context/1024 generated tokens")
        allocation = json.loads(args.allocation.read_text())
        if args.gpu_uuid not in allocation.get("allowed_compute_uuids", []) or not allocation.get("source"):
            raise ValueError("GPU UUID missing explicit allocation")
        if not re.fullmatch(r"GPU-[0-9a-fA-F-]{36}", args.gpu_uuid):
            raise ValueError("Full allocated GPU UUID required")
        report = json.loads(args.model_report.read_text())
        revision = report.get("revision")
        if report.get("model") != MODEL or not re.fullmatch(r"[0-9a-f]{40}", revision or "") or not report.get("all_files_verified"):
            raise ValueError("Fixed official verified Qwen3-8B model required")
        if args.model.resolve() != Path(report["model_directory"]).resolve() or not args.model.resolve().is_relative_to(root / "models"):
            raise ValueError("Model directory must match project-local verified report")
        files = report["files"]
        if len([f for f in files if f["filename"].endswith(".safetensors")]) != 5:
            raise ValueError("All five official shards required")
        for item in files:
            path = args.model / item["filename"]
            if not path.resolve().is_relative_to(args.model.resolve()) or stream_sha256(path) != item["sha256"]:
                raise ValueError("Local model content no longer matches verified snapshot")
        manifest, products, tasks = load_dataset(args.dataset)
        selected = sorted(tasks.values(), key=lambda t: (t["split"], t["task_id"]))[:args.limit]
        if not selected:
            raise ValueError("No train/dev review tasks")
        material = prepare_review_material(manifest, products, list(tasks.values()), seed=args.seed)
        inputs = {p["task_id"]: p for p in independent_review_inputs(material)}
        prompts = [make_independent_prompt(inputs[t["task_id"]], dataset_revision=manifest["revision"],
                                           related_tasks=list(tasks.values()),
                                           dataset_manifest_sha256=sha256_file(args.dataset / "manifest.json")) for t in selected]
        if args.prepare_only:
            os.environ.update({"CUDA_VISIBLE_DEVICES": "", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                               "HF_HOME": str(root / ".cache/huggingface"), "XDG_CACHE_HOME": str(root / ".cache"),
                               "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "2",
                               "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"})
            from transformers import AutoTokenizer
            import torch

            if torch.cuda.is_initialized():
                raise ValueError("CPU preflight must not initialize CUDA")
            tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True, trust_remote_code=False)
            rows = []
            for prompt in prompts:
                directory = args.output / "tasks" / prompt["task_id"]
                directory.mkdir(parents=True)
                write_json(directory / "prompt.json", prompt)
                messages = [{"role": "system", "content": prompt["instruction"]},
                            {"role": "user", "content": json.dumps({k: v for k, v in prompt.items()
                                                                      if k != "instruction"}, ensure_ascii=False)}]
                rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                         enable_thinking=False)
                (directory / "rendered-prompt.txt").write_text(rendered, encoding="utf-8")
                count = len(tokenizer(rendered)["input_ids"])
                rows.append({"task_id": prompt["task_id"], "task_sha256": prompt["task_sha256"],
                             "prompt_sha256": digest(prompt), "input_tokens": count,
                             "reserved_output_tokens": args.max_new_tokens,
                             "within_context_limit": count + args.max_new_tokens <= args.max_context_tokens})
            if torch.cuda.is_initialized():
                raise ValueError("Tokenizer preflight unexpectedly initialized CUDA")
            result = {"model": MODEL, "model_revision": revision, "dataset_revision": manifest["revision"],
                      "tasks": rows, "gpu_compute_performed": False, "cuda_initialized": False,
                      "model_weights_loaded": False, "model_review_performed": False,
                      "human_review_performed": False, "all_prompts_fit": all(x["within_context_limit"] for x in rows)}
            write_json(args.output / "report.json", result)
            write_json(args.output / "reviews.json", {"dataset_revision": manifest["revision"], "human_reviews": [],
                                                       "identity_reviews": [], "independent_reviews": []})
            run.record.update(execution_kind="cpu_tokenizer_prompt_preflight", model=MODEL, model_revision=revision,
                              data_revision=manifest["revision"], seed=args.seed, policy_version=PROMPT_VERSION,
                              gpu_validation="not_run_cpu_preparation_only", gpu_compute_performed=False,
                              model_review_performed=False, human_review_performed=False,
                              dependency_versions={name: importlib.metadata.version(name)
                                                   for name in ("torch", "transformers", "tokenizers", "safetensors")},
                              configuration={"thinking": False, "max_context_tokens": args.max_context_tokens,
                                             "max_new_tokens": args.max_new_tokens, "limit": args.limit,
                                             "cuda_visible_devices": "", "cpu_threads": 2},
                              runner_sha256=sha256_file(Path(__file__)),
                              dataset_manifest_sha256=sha256_file(args.dataset / "manifest.json"),
                              model_report_sha256=sha256_file(args.model_report),
                              artifact_sha256={str(p.relative_to(args.output)): sha256_file(p)
                                               for p in args.output.rglob("*") if p.is_file()
                                               and p.name not in {"run.json", "run.log"}})
            run.finish("succeeded" if result["all_prompts_fit"] else "failed", {"report": str(args.output / "report.json")},
                       "cpu_tokenizer_context_preflight_only")
            print(json.dumps({"tasks": len(rows), "all_prompts_fit": result["all_prompts_fit"], "cuda_initialized": False}))
            return 0 if result["all_prompts_fit"] else 1
        preflight = subprocess.run(["nvidia-smi", "--id=" + args.gpu_uuid,
                                    "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,driver_version",
                                    "--format=csv,noheader"], capture_output=True, text=True, check=True, timeout=15)
        write_json(args.output / "allocation.json", {"source": allocation["source"], "inherited_from": str(args.allocation),
                   "source_sha256": sha256_file(args.allocation), "selected_uuid": args.gpu_uuid,
                   "expires": allocation.get("expires"), "checked_at": timestamp(),
                   "read_only_preflight": preflight.stdout.strip(), "other_devices_used": False})
        if args.gpu_uuid not in preflight.stdout:
            raise ValueError("Read-only physical UUID check failed")
        free_mib = int(preflight.stdout.strip().split(",")[-2].strip().split()[0])
        if free_mib < 30000:
            raise ValueError("Allocated GPU currently has less than the bounded pilot's 30000MiB headroom")
        for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LIBRARY_PATH", "CPATH", "C_INCLUDE_PATH",
                     "CPLUS_INCLUDE_PATH", "PYTHONHOME", "CONDA_PREFIX", "CONDA_DEFAULT_ENV"):
            os.environ.pop(name, None)
        os.environ.update({"CUDA_VISIBLE_DEVICES": args.gpu_uuid, "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                           "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
                           "TOKENIZERS_PARALLELISM": "false", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                           "HF_HOME": str(root / ".cache/huggingface"), "XDG_CACHE_HOME": str(root / ".cache"),
                           "CUDA_CACHE_PATH": str(root / ".cache/cuda"), "CUDA_HOME": str(root / ".tools/cuda"),
                           "CUDA_PATH": str(root / ".tools/cuda"), "NVCC": str(root / ".tools/cuda/bin/nvcc"),
                           "CC": str(root / "scripts/toolchain/cc"), "CXX": str(root / "scripts/toolchain/cxx"),
                           "PATH": os.pathsep.join((str(root / ".venv-gpu/bin"), str(root / "scripts/toolchain")))})
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        torch.manual_seed(args.seed)
        if torch.cuda.device_count() != 1:
            raise ValueError("Exactly one allocated CUDA device must be visible")
        torch.cuda.init()
        run.record["gpu_compute_performed"] = True
        properties = torch.cuda.get_device_properties(0)
        actual_uuid = str(properties.uuid).lower().removeprefix("gpu-")
        if actual_uuid != args.gpu_uuid.lower().removeprefix("gpu-"):
            raise ValueError("CUDA runtime UUID mismatch")
        versions = {name: importlib.metadata.version(name) for name in ("torch", "transformers", "accelerate", "safetensors")}
        if versions["torch"] != "2.7.1+cu126" or versions["transformers"] != "4.53.2":
            raise ValueError("Existing validated candidate framework versions must be retained")
        run.record.update(model=MODEL, model_revision=revision, data_revision=manifest["revision"],
                          dataset_manifest_sha256=sha256_file(args.dataset / "manifest.json"), seed=args.seed,
                          policy_version=PROMPT_VERSION, runner_sha256=sha256_file(Path(__file__)),
                          dependency_versions=versions, gpu_uuid=args.gpu_uuid, gpu_runtime_uuid=actual_uuid,
                          gpu_name=properties.name, torch_cuda_runtime=torch.version.cuda,
                          nccl_runtime_version=torch.cuda.nccl.version(),
                          model_report_sha256=sha256_file(args.model_report), human_review_performed=False,
                          configuration={"thinking": False, "torch_dtype": "bfloat16", "attention": "sdpa",
                                         "max_context_tokens": args.max_context_tokens, "max_new_tokens": args.max_new_tokens,
                                         "concurrency": 1, "cpu_threads": 2, "temperature": 0.7, "top_p": 0.8, "top_k": 20,
                                         "do_sample": True}, sealed_or_official_task_expressions_loaded=False)
        run._save()
        tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True, trust_remote_code=False)
        model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True, trust_remote_code=False,
                                                    torch_dtype=torch.bfloat16, attn_implementation="sdpa",
                                                    device_map={"": "cuda:0"})
        model.eval()
        completed, failures = [], []
        write_json(args.output / "reviews.json", {"dataset_revision": manifest["revision"], "human_reviews": [],
                                                   "identity_reviews": [], "independent_reviews": []})
        write_json(args.output / "failures.json", failures)
        for prompt in prompts:
            task_id = prompt["task_id"]
            directory = args.output / "tasks" / task_id
            directory.mkdir(parents=True)
            write_json(directory / "prompt.json", prompt)
            messages = [{"role": "system", "content": prompt["instruction"]},
                        {"role": "user", "content": json.dumps({k: v for k, v in prompt.items() if k != "instruction"}, ensure_ascii=False)}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            (directory / "rendered-prompt.txt").write_text(rendered, encoding="utf-8")
            encoded = tokenizer(rendered, return_tensors="pt")
            input_tokens = encoded["input_ids"].shape[-1]
            if input_tokens + args.max_new_tokens > args.max_context_tokens:
                failures.append({"task_id": task_id, "error": "context_limit", "input_tokens": input_tokens})
                continue
            encoded = encoded.to("cuda:0")
            started = time.monotonic()
            with torch.inference_mode():
                generated = model.generate(**encoded, max_new_tokens=args.max_new_tokens, do_sample=True,
                                           temperature=0.7, top_p=0.8, top_k=20, use_cache=True,
                                           pad_token_id=tokenizer.eos_token_id)
            torch.cuda.synchronize()
            tokens = generated[0, input_tokens:].tolist()
            raw = {"generated_text": tokenizer.decode(tokens, skip_special_tokens=True), "generated_token_ids": tokens,
                   "input_tokens": input_tokens, "output_tokens": len(tokens),
                   "finish_reason": "length" if len(tokens) == args.max_new_tokens else "eos",
                   "elapsed_seconds": time.monotonic() - started}
            write_json(directory / "response.json", raw)
            try:
                if raw["finish_reason"] == "length":
                    raise ValueError("Output reached token limit")
                parsed = parse_independent_response(raw["generated_text"])
                review = {"task_id": task_id, "task_sha256": prompt["task_sha256"], "status": "completed",
                          **parsed, "model": MODEL, "model_revision": revision, "reviewed_at": timestamp(),
                          "dataset_revision": manifest["revision"], "prompt_version": PROMPT_VERSION,
                          "prompt": prompt, "prompt_sha256": digest(prompt), "raw_response": raw,
                          "response_sha256": digest(raw), "prompt_path": str(directory / "prompt.json"),
                          "response_path": str(directory / "response.json"), "gpu_uuid": args.gpu_uuid,
                          "independence_basis": {"method": "different_model", "generation_models": ["deepseek-flash"],
                                                 "generation_model_role": "expert_trajectory_teacher",
                                                 "task_expression_generation": "deterministic builder; no model expression augmentation"}}
                write_json(directory / "review.json", review)
                completed.append(review)
                print(json.dumps({"task_id": task_id, "decision": review["decision"], "input_tokens": input_tokens,
                                  "output_tokens": len(tokens)}), flush=True)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                failures.append({"task_id": task_id, "error": type(exc).__name__, "detail": str(exc)})
            write_json(args.output / "reviews.json", {"dataset_revision": manifest["revision"], "human_reviews": [],
                                                       "identity_reviews": [], "independent_reviews": completed})
            write_json(args.output / "failures.json", failures)
        result = {"model": MODEL, "model_revision": revision, "dataset_revision": manifest["revision"],
                  "tasks_attempted": len(prompts), "completed_reviews": len(completed),
                  "accepted": sum(r["decision"] == "accept" for r in completed),
                  "rejected": sum(r["decision"] == "reject" for r in completed), "failures": failures,
                  "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                  "gpu_peak_reserved_bytes": torch.cuda.max_memory_reserved(), "human_review_performed": False,
                  "formal_release_approved": False, "training_performed": False}
        write_json(args.output / "report.json", result)
        artifacts = {"reviews": str(args.output / "reviews.json"), "report": str(args.output / "report.json")}
        run.record["gpu_validation"] = "real_independent_semantic_inference_completed"
        run.record["artifact_sha256"] = {str(p.relative_to(args.output)): sha256_file(p)
                                          for p in args.output.rglob("*") if p.is_file() and p.name not in {"run.json", "run.log"}}
        run.finish("succeeded" if not failures else "partial", artifacts, "real_allocated_gpu_model_review")
        return 0 if not failures else 1
    except BaseException as exc:
        run.finish("failed", artifacts, "independent_review_not_completed", type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
