from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import threading
import re

from .utils import run_command, ensure_dir, print_spinner

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s or "")

@dataclass
class BidsValidationResult:
    status: str           # "SUCCESS" | "ISSUES_FOUND" | "FAILED"
    returncode: int
    stdout: str
    stderr: str
    output_file: Path

def validate_bids(*, bids_folder: Path, output_dir: Path) -> BidsValidationResult:
    ensure_dir(output_dir)

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = output_dir / f"bids_validator_output_{date_str}.txt"

    bids_folder = bids_folder.expanduser().resolve()

    cmd = ["deno", "run", "-ERWN", "jsr:@bids/validator", str(bids_folder)]

    stop = {"flag": False}
    spinner_thread = threading.Thread(
        target=print_spinner,
        args=(lambda: stop["flag"], "Running BIDS validator..."),
        daemon=True,
    )
    spinner_thread.start()

    try:
        res = run_command(cmd, capture_output=True, check=False)
        rc = res.returncode
        stdout = strip_ansi(res.stdout)
        stderr = strip_ansi(res.stderr)

        if rc == 0:
            status = "SUCCESS"
        else:
            status = "ISSUES_FOUND"

    except Exception as e:
        rc = 1
        status = "FAILED"
        stdout, stderr = "", strip_ansi(str(e))

    finally:
        stop["flag"] = True
        spinner_thread.join()

    # Friendly top-line summary
    summary_lines = []
    summary_lines.append(f"DATASET: {bids_folder}")
    summary_lines.append(f"RETURN CODE: {rc}")
    summary_lines.append(f"STATUS: {status}")

    # If the dataset path doesn't exist, make that extremely obvious
    if not bids_folder.exists():
        summary_lines.append("")
        summary_lines.append("!! PATH ERROR: dataset folder does not exist on disk.")
        summary_lines.append("   Check spelling / mount / volume name.")
        summary_lines.append(f"   Provided path: {bids_folder}")

    summary = "\n".join(summary_lines)

    out_path.write_text(
        summary
        + "\n\n"
        + "========== STDOUT (cleaned) ==========\n"
        + (stdout if stdout.strip() else "(no stdout)\n")
        + "\n"
        + "========== STDERR (cleaned) ==========\n"
        + (stderr if stderr.strip() else "(no stderr)\n"),
        encoding="utf-8",
    )

    return BidsValidationResult(
        status=status,
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
        output_file=out_path,
    )
