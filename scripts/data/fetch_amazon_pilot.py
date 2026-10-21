"""Fetch a bounded pinned Amazon metadata row group with auditable HTTP ranges.

Input is a new output directory. Output contains raw rows, pinned repository card,
request status/byte hashes and errors. This one-time provenance tool imports only
stdlib and installed PyArrow; offline S2 normalization does not depend on it.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import platform
import sys
import importlib.metadata
from pathlib import Path
import urllib.request
from datetime import datetime, timezone

REVISION = '2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e'
URL = ('https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/'
       + REVISION + '/raw_meta_Electronics/full-00000-of-00010.parquet')
CAP = 256 * 1024 * 1024

class HTTPRangeFile(io.RawIOBase):
    """Seekable read-only range stream, bounded by a cumulative byte budget."""
    def __init__(self, directory: Path):
        self.directory, self.position, self.transferred = directory, 0, 0
        self.requests = []
        self.size = None
        self._fetch(0, 0)

    def _fetch(self, start: int, end: int) -> bytes:
        request = urllib.request.Request(URL, headers={'Range': f'bytes={start}-{end}'})
        with urllib.request.urlopen(request, timeout=90) as response:
            content_range = response.headers.get('Content-Range', '')
            if response.status != 206 or not content_range.startswith(f'bytes {start}-'):
                raise RuntimeError(f'Range ignored: {response.status} {content_range}')
            expected = end - start + 1
            if self.transferred + expected > CAP:
                raise RuntimeError('256 MiB metadata transfer cap reached')
            data = response.read(expected + 1)
            if len(data) != expected:
                raise RuntimeError('Wrong range length')
            self.size = int(content_range.split('/')[-1])
            self.transferred += len(data)
            number = len(self.requests)
            filename = f'range-{number:03}-{start}-{end}.bin'
            (self.directory / filename).write_bytes(data)
            self.requests.append({'url': URL, 'range': [start, end], 'status': response.status,
                                  'content_range': content_range, 'bytes': len(data),
                                  'sha256': hashlib.sha256(data).hexdigest(), 'file': filename})
            self.save_manifest()
            return data

    def save_manifest(self):
        (self.directory / 'ranges.json').write_text(json.dumps({
            'revision': REVISION, 'url': URL, 'file_size': self.size,
            'transferred_bytes': self.transferred, 'requests': self.requests,
            'retrieved_at': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position
    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if position < 0: raise ValueError('Negative position')
        self.position = position
        return position
    def read(self, length=-1):
        if length < 0: length = self.size - self.position
        length = min(length, self.size - self.position)
        if length <= 0: return b''
        data = self._fetch(self.position, self.position + length - 1)
        self.position += len(data)
        return data
    def readinto(self, buffer):
        data = self.read(len(buffer)); buffer[:len(data)] = data; return len(data)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('This source fetch must hide all GPUs')
    args.output.mkdir(parents=True, exist_ok=False)
    run = {'stage':'S2','execution_kind':'cpu_source_retrieval',
           'started_at':datetime.now(timezone.utc).isoformat(),
           'argv':sys.argv,'interpreter':sys.executable,'python_version':sys.version,
           'machine':platform.node(),'platform':platform.platform(),
           'source_revision':REVISION,'source_url':URL,'byte_cap':CAP,
           'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'cuda_visible_devices':'','gpu_context_created':False,'teacher_calls':0,
           'model_revision':None,'seed':None,'checkpoint':None,'status':'running'}
    (args.output/'run.json').write_text(json.dumps(run,indent=2)+'\n')
    source = None
    try:
        import pyarrow.parquet as parquet
        run['pyarrow_version'] = importlib.metadata.version('pyarrow')
        source = HTTPRangeFile(args.output)
        data = parquet.ParquetFile(source)
        print('rowgroups', data.num_row_groups, 'schema', data.schema.names, flush=True)
        columns = ['main_category','title','price','store','categories','details','parent_asin']
        rows = data.read_row_group(0, columns=columns).to_pylist()
        (args.output/'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
        print('records',len(rows),'transferred_bytes',source.transferred,flush=True)
        run.update(status='success',row_count=len(rows),transferred_bytes=source.transferred)
    except BaseException as error:
        run.update(status='failed',error_type=type(error).__name__,error=str(error))
        (args.output/'error.json').write_text(json.dumps({'type':type(error).__name__,'message':str(error)},indent=2)+'\n')
        raise
    finally:
        if source is not None: source.save_manifest()
        run['finished_at'] = datetime.now(timezone.utc).isoformat()
        run['artifacts'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in args.output.iterdir() if p.is_file() and p.name != 'run.json'}
        (args.output/'run.json').write_text(json.dumps(run,indent=2)+'\n')

if __name__ == '__main__': main()
