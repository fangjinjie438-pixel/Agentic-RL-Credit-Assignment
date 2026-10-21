"""Run one command after the user's proxy_on, without sourcing other shell setup.

Called using project .venv-cpu Python. Reads only the named proxy_on function
from the user's shell rc, invokes it in a clean bash, then execs the argument
vector. Proxy credentials/function text are never printed or persisted.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re


def main() -> None:
    """Execute the explicit command with proxy exports; do not run global setup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rc-file", type=Path, default=Path("~/.bashrc").expanduser())
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a command after --")
    text = args.rc_file.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^(?:function\s+)?proxy_on\s*\(\)\s*\{.*?^\}", text)
    if match is None:
        parser.error("proxy_on function not found; source the proxy manually in your own terminal")
    shell = "set -e\n" + match.group(0) + '\nproxy_on >/dev/null 2>&1\nexec "$@"'
    # Pass rc content through a private inherited pipe, not process argv where
    # proxy credentials could become visible in process listings.
    read_fd, write_fd = os.pipe()
    os.set_inheritable(read_fd, True)
    payload = shell.encode("utf-8")
    if len(payload) > 4096:
        os.close(read_fd)
        os.close(write_fd)
        parser.error("proxy_on definition is unexpectedly large; enable it manually")
    os.write(write_fd, payload)
    os.close(write_fd)
    os.execv("/bin/bash", ["bash", "--noprofile", "--norc", f"/dev/fd/{read_fd}", *command])


if __name__ == "__main__":
    main()
