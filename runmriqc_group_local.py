#!/usr/bin/env python3


# Runmriqc_group_local
# Sarah Hennessy
# 1/4/26 last edit


"""
Aggregate already-run MRIQC IQM JSONs into group TSVs 

Usage examples
--------------

Weekly option: Aggregate already-run MRIQC IQM JSONs into FOUR group TSVs:

1) baseline_T1w_{todays date}.tsv   (sub-####)
2) baseline_bold_{todays date}.tsv  (sub-####)
3) scan2_T1w_{todays date}.tsv      (sub-####1)
4) scan2_bold_{todays date}.tsv     (sub-####1)


# Aggregate ALL subjects found in derivatives:
--mriqc-deriv /PATH To/mriqc_dev
output: baseline_T1w.tsv etc.

# Aggregate only specific subjects (labels WITHOUT "sub-"):
# (for example, as used in master_mriqc.py)
 --mriqc-deriv /PATH To/mriqc_dev --subjects 1001 1002 1044

# if you choose this option, it will also add those subjects to the overall spreadsheet for full sample comparisons.

# Same, but allow "sub-" prefix too:
 --mriqc-deriv /PATH To/mriqc_dev --subjects sub-1001 sub-1002

# Write outputs somewhere else:
 --mriqc-deriv /PATH To/mriqc_dev --out-dir /PATH To/mriqc_dev
"""


from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, Literal, Optional
from datetime import datetime


import pandas as pd

Modality = Literal["T1w", "bold"]


BASELINE_DIR_RE = re.compile(r"^sub-(\d{4})$")
SCAN2_DIR_RE = re.compile(r"^sub-(\d{4}1)$")  # e.g., sub-12341


def _safe_read_json(p: Path) -> dict:
    try:
        with p.open("r") as f:
            return json.load(f)
    except Exception as e:
        return {"__read_error__": f"{type(e).__name__}: {e}", "__path__": str(p)}


def _flatten(d: dict, prefix: str = "", sep: str = ".") -> dict:
    out: dict = {}
    for k, v in (d or {}).items():
        key = f"{prefix}{sep}{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten(v, key, sep=sep))
        else:
            out[key] = v
    return out


def parse_subject_labels(raw: Optional[Iterable[str]]) -> Optional[list[str]]:
    """
    Accepts '1001'/'sub-1001' and also '10011'/'sub-10011'.
    Returns list of IDs without 'sub-' prefix, or None.
    """
    if raw is None:
        return None
    out: list[str] = []
    for s in raw:
        s = str(s).strip()
        if not s:
            continue
        if s.startswith("sub-"):
            s = s[4:]
        out.append(s)
    return out if out else None


def split_baseline_scan2(labels: Optional[Iterable[str]]) -> tuple[Optional[list[str]], Optional[list[str]]]:
    """
    Split provided labels into baseline (####) vs scan2 (####1).
    Returns (baseline_labels, scan2_labels). Either may be empty/None.
    """
    if labels is None:
        return None, None

    baseline: list[str] = []
    scan2: list[str] = []
    for lab in labels:
        lab = str(lab)
        if re.fullmatch(r"\d{4}", lab):
            baseline.append(lab)
        elif re.fullmatch(r"\d{4}1", lab):
            scan2.append(lab)
        else:
            raise ValueError(
                f"Subject label '{lab}' does not match baseline (####) or scan2 (####1). "
                "Pass labels like 1001 or 10011 (or sub-1001/sub-10011)."
            )

    return (baseline or None), (scan2 or None)


def discover_labels_from_derivatives(mriqc_deriv_dir: Path) -> tuple[list[str], list[str]]:
    """
    Discover baseline and scan2 labels from subject directories in MRIQC derivatives.
    Returns lists WITHOUT 'sub-' prefix:
      baseline: ['1001', '1002', ...]
      scan2:    ['10011', '10021', ...]
    """
    baseline: list[str] = []
    scan2: list[str] = []

    for p in sorted(mriqc_deriv_dir.glob("sub-*")):
        if not p.is_dir():
            continue
        m0 = BASELINE_DIR_RE.match(p.name)
        if m0:
            baseline.append(m0.group(1))
            continue
        m1 = SCAN2_DIR_RE.match(p.name)
        if m1:
            scan2.append(m1.group(1))
            continue

    return baseline, scan2


def find_iqm_jsons(
    mriqc_deriv_dir: Path,
    modality: Modality,
    participant_labels: Optional[Iterable[str]] = None,
) -> list[Path]:
    """
    Locate IQM JSON files in MRIQC derivatives for a modality.
    If participant_labels is provided, keep only those IDs (without sub- prefix).
    """
    if modality == "T1w":
        candidates = list(mriqc_deriv_dir.glob("sub-*/anat/sub-*_T1w.json"))
    else:
        candidates = list(mriqc_deriv_dir.glob("sub-*/func/sub-*_bold.json"))

    # None means "no filter" => return all candidates
    if participant_labels is None:
        return sorted(candidates)

    # Empty list means "filter provided but nothing requested" => return nothing
    participant_labels = list(participant_labels)
    if len(participant_labels) == 0:
        return []

    want = {str(x).replace("sub-", "") for x in participant_labels}

    kept: list[Path] = []
    for p in candidates:
        m = re.search(r"sub-(\d+)", p.name)
        if m and m.group(1) in want:
            kept.append(p)

    return sorted(kept)


def aggregate_iqms(
    mriqc_deriv_dir: Path,
    modality: Modality,
    participant_labels: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    json_paths = find_iqm_jsons(mriqc_deriv_dir, modality, participant_labels)
    rows: list[dict] = []

    for jp in json_paths:
        d = _safe_read_json(jp)
        flat = _flatten(d)

        m = re.search(r"sub-(\d+)", jp.name)
        pid = m.group(1) if m else None

        flat["participant_id"] = pid
        flat["file_name"] = jp.name
        flat["source_json"] = str(jp)
        rows.append(flat)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    first_cols = ["participant_id", "file_name", "source_json"]
    cols = first_cols + [c for c in df.columns if c not in first_cols]
    df = df.loc[:, cols].sort_values(["participant_id", "file_name"], na_position="last").reset_index(drop=True)
    return df


def add_outlier_flags(df: pd.DataFrame, z_thresh: float = 3.0) -> pd.DataFrame:
    out = df.copy()
    num_cols = out.select_dtypes(include="number").columns.tolist()

    for c in num_cols:
        s = out[c]
        if s.notna().sum() < 5:
            continue
        std = s.std(skipna=True)
        if std == 0 or pd.isna(std):
            continue
        z = (s - s.mean(skipna=True)) / std
        out[f"outlier__{c}"] = z.abs() >= z_thresh

    return out

def upsert_group_tsv(
    df_new: pd.DataFrame,
    canonical_path: Path,
    key_cols: list[str] = ["participant_id", "file_name"],
) -> None:
    """
    Merge df_new into an existing canonical TSV (or create it if missing).
    De-dupes on key_cols (keeps the latest df_new row if duplicates exist).
    """
    if canonical_path.exists():
        df_old = pd.read_csv(canonical_path, sep="\t")
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new.copy()

    # Drop exact duplicates by keys, keeping the last occurrence (new wins)
    df_all = df_all.drop_duplicates(subset=key_cols, keep="last")

    # Nice stable sort if keys exist
    sort_cols = [c for c in key_cols if c in df_all.columns]
    if sort_cols:
        df_all = df_all.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_csv(canonical_path, sep="\t", index=False)


def write_one(
    mriqc_deriv: Path,
    out_dir: Path,
    label_set_name: str,   # "baseline" or "scan2"
    labels: Optional[list[str]],
    modality: Modality,
    add_outliers: bool,
    z_thresh: float,
    incremental: bool = False,
) -> None:

    # If labels were explicitly provided but there are none for this group, skip.
    # (This prevents baseline->scan2 contamination.)
    if incremental and labels is None:
        print(f"[INFO] Incremental run: no labels provided for {label_set_name} {modality}; skipping.")
        return
    if labels is not None and len(labels) == 0:
        print(f"[INFO] No labels for {label_set_name} {modality}; skipping.")
        return



    df = aggregate_iqms(mriqc_deriv, modality, participant_labels=labels)

    if df.empty:
        print(f"[WARN] No rows for {label_set_name} {modality} (labels={labels}).")
        return

    if add_outliers:
        df = add_outlier_flags(df, z_thresh=z_thresh)

    metric_cols = df.select_dtypes(include="number").columns.tolist()
    keep_cols = ["participant_id", "file_name"] + metric_cols
    df = df[keep_cols]

    today = datetime.now().strftime("%Y-%m-%d")
    dated_path = out_dir / f"{label_set_name}_{modality}_{today}.tsv"
    df.to_csv(dated_path, sep="\t", index=False)
    print(f"Wrote snapshot {dated_path} (rows={len(df):,}, cols={len(df.columns):,})")

    if incremental:
        canonical_path = out_dir / f"{label_set_name}_{modality}.tsv"
        upsert_group_tsv(df, canonical_path, key_cols=["participant_id", "file_name"])
        print(f"Updated canonical {canonical_path} (+{len(df):,} candidate rows, deduped by participant_id+file_name)")




def main() -> None:
    ap = argparse.ArgumentParser(description="Write baseline/scan2 MRIQC group TSVs (T1w + bold).")
    ap.add_argument("--mriqc-deriv", required=True, type=Path,
                    help="MRIQC derivatives dir containing sub-*/anat and sub-*/func.")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Output directory for TSVs (default: --mriqc-deriv).")
    ap.add_argument("--subjects", nargs="*", default=None,
                    help="Optional list of subjects to include. Accepts baseline #### and scan2 ####1 "
                         "(with or without 'sub-'). If omitted, aggregates ALL baseline + scan2 found.")
    ap.add_argument("--no-outliers", action="store_true",
                    help="Do not add outlier flag columns.")
    ap.add_argument("--z-thresh", type=float, default=3.0,
                    help="Z-score threshold for outlier flags (default: 3.0).")

    args = ap.parse_args()

    mriqc_deriv = args.mriqc_deriv.expanduser().resolve()
    out_dir = (args.out_dir.expanduser().resolve() if args.out_dir else mriqc_deriv)
    out_dir.mkdir(parents=True, exist_ok=True)

    user_labels = parse_subject_labels(args.subjects)
    incremental = (user_labels is not None)  # only incremental when a subset was requested

    baseline_labels, scan2_labels = split_baseline_scan2(user_labels)

    if user_labels is None:
        # Aggregate ALL: discover from derivatives
        baseline_labels, scan2_labels = discover_labels_from_derivatives(mriqc_deriv)
        # baseline_labels = baseline_labels or None
        # scan2_labels = scan2_labels or None
        print(f"Discovered baseline subjects: {0 if baseline_labels is None else len(baseline_labels)}")
        print(f"Discovered scan2 subjects:    {0 if scan2_labels is None else len(scan2_labels)}")
    else:
        print(f"Using provided baseline subjects: {0 if baseline_labels is None else len(baseline_labels)}")
        print(f"Using provided scan2 subjects:    {0 if scan2_labels is None else len(scan2_labels)}")

    add_outliers = not args.no_outliers

    # Always write four outputs (warnings if any are empty)

    for modality in ("T1w", "bold"):
        write_one(
            mriqc_deriv, out_dir, "baseline", baseline_labels, modality,
            add_outliers, args.z_thresh,
            incremental=incremental
        )
        write_one(
            mriqc_deriv, out_dir, "scan2", scan2_labels, modality,
            add_outliers, args.z_thresh,
            incremental=incremental
        )


if __name__ == "__main__":
    main()

