"""Fetch the fixed official Qwen3-8B snapshot for S2 independent review.

Input is an exact HF commit and a new evidence directory. The CPU-only standard
library downloader stores files under project models/, checks every LFS SHA256
and every regular Git blob SHA1, and writes machine/command/source evidence.
It never imports a model or creates a CUDA context. Interrupted .part downloads
can be resumed by a new evidence run; existing complete files are reverified.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

from procure_rl.runtime import RunRecord, sha256_file

REPOSITORY = "Qwen/Qwen3-8B"
FILES = {"README.md", "config.json", "generation_config.json", "merges.txt",
         "model.safetensors.index.json", "tokenizer.json", "tokenizer_config.json", "vocab.json"}


def selected_files(metadata: dict, revision: str) -> list[dict]:
    """Require a fixed official snapshot with all five expected weight shards."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or metadata.get("sha") != revision:
        raise ValueError("Exact model revision mismatch")
    names = FILES | {f"model-{i:05d}-of-00005.safetensors" for i in range(1, 6)}
    selected = [item for item in metadata["siblings"] if item["rfilename"] in names]
    if {item["rfilename"] for item in selected} != names:
        raise ValueError("Official snapshot missing required files")
    for item in selected:
        if type(item.get("size")) is not int or item["size"] <= 0:
            raise ValueError("Missing source file size")
        if item["rfilename"].endswith("safetensors") and not item.get("lfs", {}).get("sha256"):
            raise ValueError("Weight SHA256 absent")
    return selected


def verify_file(path: Path, item: dict) -> dict:
    """Compare complete local bytes to the official content identifier."""
    if path.stat().st_size != item["size"]:
        raise ValueError("Downloaded size mismatch: " + path.name)
    sha256 = hashlib.sha256()
    git_sha1 = hashlib.sha1(f"blob {item['size']}\0".encode())
    with path.open("rb") as handle:
        while data := handle.read(8 * 1024 * 1024):
            sha256.update(data)
            git_sha1.update(data)
    expected = item.get("lfs", {}).get("sha256")
    if expected and sha256.hexdigest() != expected:
        raise ValueError("Downloaded SHA256 mismatch: " + path.name)
    if not expected and git_sha1.hexdigest() != item["blobId"]:
        raise ValueError("Downloaded Git blob mismatch: " + path.name)
    return {"filename": path.name, "bytes": item["size"], "sha256": sha256.hexdigest(),
            "source_lfs_sha256": expected, "source_git_blob_sha1": item["blobId"], "verified": True}


def fetch_file(directory: Path, revision: str, item: dict, *,
               transport_base_url: str = "https://huggingface.co", direct: bool = False) -> dict:
    """Resume one bounded public file and atomically accept only verified bytes."""
    name = item["rfilename"]
    path = directory / name
    source_url = f"https://huggingface.co/{REPOSITORY}/resolve/{revision}/{name}"
    url = f"{transport_base_url}/{REPOSITORY}/resolve/{revision}/{name}"
    if path.exists():
        return {**verify_file(path, item), "official_url": source_url, "transport_url": url, "downloaded_bytes": 0}
    partial = path.with_name(name + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > item["size"]:
        raise ValueError("Partial file too large")
    if offset < item["size"]:
        headers = {"User-Agent": "Procure-RL-S2-model-integrity/1"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct else urllib.request.build_opener()
        with opener.open(request, timeout=90) as response:
            if response.status != (206 if offset else 200):
                raise ValueError("Unexpected range response")
            if offset and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                raise ValueError("Unexpected content range")
            size = offset
            with partial.open("ab" if offset else "wb") as handle:
                while data := response.read(8 * 1024 * 1024):
                    size += len(data)
                    if size > item["size"]:
                        raise ValueError("Response exceeds expected size")
                    handle.write(data)
    result = verify_file(partial, item)
    partial.replace(path)
    print(json.dumps({"verified_file": name, "bytes": item["size"]}), flush=True)
    return {**result, "filename": name, "official_url": source_url, "transport_url": url,
            "transport_proxy_disabled": direct, "resumed_bytes": offset, "downloaded_bytes": item["size"] - offset}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--transport-base-url", choices=("https://huggingface.co", "https://hf-mirror.com"),
                        default="https://huggingface.co")
    parser.add_argument("--direct-transport", action="store_true")
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    run = RunRecord(args.output, root, [sys.executable, *sys.argv],
                    execution_kind="cpu_public_model_download", stage="S2")
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
            raise ValueError("Exact commit required")
        url = f"https://huggingface.co/api/models/{REPOSITORY}/revision/{args.revision}?blobs=true"
        with urllib.request.urlopen(url, timeout=45) as response:
            source = response.read(4 * 1024 * 1024)
        (args.output / "hf-source.json").write_bytes(source)
        metadata = json.loads(source)
        files = selected_files(metadata, args.revision)
        directory = root / "models/Qwen3-8B" / args.revision
        directory.mkdir(parents=True, exist_ok=True)
        run.record.update(model_revision=args.revision, model=REPOSITORY,
                          runner_sha256=sha256_file(Path(__file__)), source_url=url,
                          model_directory=str(directory), seed=None, network_concurrency=args.workers,
                          transport_base_url=args.transport_base_url, transport_proxy_disabled=args.direct_transport)
        run._save()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(lambda item: fetch_file(directory, args.revision, item,
                                      transport_base_url=args.transport_base_url, direct=args.direct_transport), files))
        report = {"model": REPOSITORY, "revision": args.revision, "source_url": url,
                  "model_directory": str(directory), "files": results,
                  "all_files_verified": True, "gpu_compute_performed": False}
        (args.output / "model-verified.json").write_text(json.dumps(report, indent=2) + "\n")
        run.record["artifact_sha256"] = {"model-verified.json": sha256_file(args.output / "model-verified.json"),
                                         "hf-source.json": sha256_file(args.output / "hf-source.json")}
        run.finish("succeeded", {"model": str(directory), "report": str(args.output / "model-verified.json")},
                   "official_snapshot_all_content_hashes_verified_cpu_only")
        return 0
    except BaseException as exc:
        run.finish("failed", {}, "model_download_not_complete", type(exc).__name__)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
