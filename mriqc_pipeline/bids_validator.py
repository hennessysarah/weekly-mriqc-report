# bids validator for weekly mriqc script

# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 4, 2026


from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import threading

from .utils import run_command, ensure_dir, print_spinner

@dataclass
class BidsValidationResult:
    status: str           # "SUCCESS" | "ISSUES_FOUND" | "FAILED"
    returncode: int
    stdout: str
    stderr: str
    output_file: Path

def validate_bids(*, bids_folder: Path, output_dir: Path) -> BidsValidationResult:
    """
    Runs: deno run -ERWN jsr:@bids/validator <dataset>
    Saves stdout/stderr + rc to a dated file.
    """
    ensure_dir(output_dir)

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = output_dir / f"bids_validator_output_{date_str}.txt"

    cmd = ["deno", "run", "-ERWN", "jsr:@bids/validator", str(bids_folder)]

    stop = {"flag": False}
    spinner_thread = threading.Thread(target=print_spinner, args=(lambda: stop["flag"], "Running BIDS validator..."))
    spinner_thread.start()

    try:
        res = run_command(cmd, capture_output=True, check=False)
        rc = res.returncode
        status = "SUCCESS" if rc == 0 else "ISSUES_FOUND"
        stdout, stderr = res.stdout, res.stderr
    except Exception as e:
        rc = 1
        status = "FAILED"
        stdout, stderr = "", str(e)
    finally:
        stop["flag"] = True
        spinner_thread.join()

    out_path.write_text(
        "RETURN CODE:\n"
        f"{rc}\n\n"
        "STDOUT:\n"
        f"{stdout}\n\n"
        "STDERR:\n"
        f"{stderr}\n",
        encoding="utf-8",
    )

    return BidsValidationResult(status=status, returncode=rc, stdout=stdout, stderr=stderr, output_file=out_path)
