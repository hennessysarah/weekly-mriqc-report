# mriqc_local.py
# for weekly mriqc script

# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 4, 2026



from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import re
import threading

from .utils import run_command, ensure_dir, print_spinner

def extract_id_num(sub_id: str) -> str | None:
    m = re.match(r"sub-(\d+)", str(sub_id))
    return m.group(1) if m else None

def load_scan_presence(csv_paths: list[Path]) -> pd.DataFrame:
    dfs = []
    for p in csv_paths:
        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")
        df = pd.read_csv(p)
        df["source_csv"] = p.name
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

def find_missing_mriqc_ids(df: pd.DataFrame, mriqc_col: str = "MRIQC", id_col: str = "ID") -> list[str]:
    col = df[mriqc_col]
    mask_missing = (col == 0) | (col == "0") | (col.astype(str).str.strip() == "0")
    missing_df = df.loc[mask_missing].copy()
    missing_df["id_num"] = missing_df[id_col].apply(extract_id_num)
    missing_df = missing_df.dropna(subset=["id_num"])
    return list(missing_df["id_num"])

@dataclass
class LocalRunSummary:
    targets: list[str]
    n_ok: int
    n_err: int
    logs_dir: Path

def run_mriqc_for_ids(
    *,
    mriqc_script: Path,
    targets: list[str],
    logs_dir: Path,
    timeout_seconds: int | None = None,
    dry_run: bool = False,
) -> LocalRunSummary:
    if not mriqc_script.exists():
        raise FileNotFoundError(f"run_mriqc_local.sh not found at: {mriqc_script}")

    ensure_dir(logs_dir)

    n_ok = 0
    n_err = 0

   # from tqdm import tqdm

   
    #for id_num in tqdm(targets, desc="Running MRIQC", unit="sub"):
    for id_num in targets:
      #  print()
        stop = {"flag": False}
        spinner_thread = threading.Thread(
            target=print_spinner,
            args=(lambda: stop["flag"], f"starting {id_num}"),
            daemon=True,
        )
        spinner_thread.start()

        cmd = ["bash", str(mriqc_script), str(id_num)]
        print("Command:")
        print(str(cmd))
        if dry_run:
            continue

        res = run_command(cmd, capture_output=True, check=False, timeout=timeout_seconds)

        out_path = logs_dir / f"mriqc_{id_num}.out.txt"
        err_path = logs_dir / f"mriqc_{id_num}.err.txt"
        out_path.write_text(res.stdout, encoding="utf-8")
        err_path.write_text(res.stderr, encoding="utf-8")
        print(f"log written at: {out_path}")

        if res.returncode == 0:
            n_ok += 1
        else:
            n_err += 1
        stop["flag"] = True
        spinner_thread.join()

    return LocalRunSummary(targets=targets, n_ok=n_ok, n_err=n_err, logs_dir=logs_dir)
