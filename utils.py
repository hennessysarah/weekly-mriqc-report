#utils.py

# Util functions for the weekly MRIQC script

# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 4, 2026


from __future__ import annotations
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

SPINNER_CHARS = ["-", "\\", "|", "/"]

@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

def run_command(
    command: list[str],
    *,
    capture_output: bool = True,
    check: bool = False,
    timeout: Optional[int] = None,
) -> CommandResult:
    """Run a command and return (rc, stdout, stderr)."""
    proc = subprocess.run(
        command,
        capture_output=capture_output,
        text=True,
        check=False,     # we control raising below
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command, proc.stdout, proc.stderr)
    return CommandResult(proc.returncode, proc.stdout or "", proc.stderr or "")

def spinner_start():
    """Yield spinner frames forever; used by print_spinner()."""
    i = 0
    while True:
        yield SPINNER_CHARS[i % len(SPINNER_CHARS)]
        i += 1

def print_spinner(stop_flag_callable, prefix="Working..."):
    frames = spinner_start()
    while not stop_flag_callable():
        sys.stdout.write(f"\r{prefix} {next(frames)}")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
