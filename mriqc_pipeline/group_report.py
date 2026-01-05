# group report.py

# for weekly mriqc script

# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 4, 2026



from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import pandas as pd

from .utils import run_command
from .plotting import plot_mriqc_boxplots

T1_METRICS_DEFAULT = ["cjv", "cnr", "qi_2"]
BOLD_METRICS_DEFAULT = ["fd_mean", "snr", "dvars_nstd"]

@dataclass
class ReportArtifacts:
    # figure paths keyed by CID used in the email
    cid_to_path: dict[str, Path]
    # n's shown next to each panel label
    counts: dict[str, int]  # keys: baseline_t1, baseline_rest, baseline_ta, scan2_t1, scan2_rest, scan2_ta


def run_group_mriqc(*, script_path: Path, deriv_dir: Path, out_dir: Path, targets: list[str]) -> None:
    cmd = [
        "python",
        str(script_path),
        "--mriqc-deriv", str(deriv_dir),
        "--out-dir", str(out_dir),
    ]

    # Only include --subjects if we actually have a subset to request
    if targets:
        cmd += ["--subjects", *[str(t) for t in targets]]

    run_command(cmd, capture_output=False, check=True)


def _load_tsvs(out_dir: Path, today: str) -> dict[str, pd.DataFrame]:
    out_dir = Path(out_dir)

    dfs = {
        "s1_t1": pd.read_csv(out_dir / f"baseline_T1w_{today}.tsv", sep="\t"),
        "s1_bold": pd.read_csv(out_dir / f"baseline_bold_{today}.tsv", sep="\t"),
        "s2_t1": pd.read_csv(out_dir / f"scan2_T1w_{today}.tsv", sep="\t"),
        "s2_bold": pd.read_csv(out_dir / f"scan2_bold_{today}.tsv", sep="\t"),
        "s1_t1_full": pd.read_csv(out_dir / "baseline_T1w.tsv", sep="\t"),
        "s1_bold_full": pd.read_csv(out_dir / "baseline_bold.tsv", sep="\t"),
        "s2_t1_full": pd.read_csv(out_dir / "scan2_T1w.tsv", sep="\t"),
        "s2_bold_full": pd.read_csv(out_dir / "scan2_bold.tsv", sep="\t"),
    }
    return dfs

def _split_bold(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    # kind in {"rest", "ta"}
    return df[df["file_name"].str.contains(kind, case=False, na=False)]

def make_weekly_figures(
    *,
    out_dir: Path,
    today: str | None = None,
    t1_metrics = T1_METRICS_DEFAULT,
    bold_metrics = BOLD_METRICS_DEFAULT,
) -> ReportArtifacts:
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")

    dfs = _load_tsvs(out_dir, today)

    rest_s1 = _split_bold(dfs["s1_bold"], "rest")
    ta_s1   = _split_bold(dfs["s1_bold"], "ta")
    rest_s2 = _split_bold(dfs["s2_bold"], "rest")
    ta_s2   = _split_bold(dfs["s2_bold"], "ta")

    rest_s1_full = _split_bold(dfs["s1_bold_full"], "rest")
    ta_s1_full   = _split_bold(dfs["s1_bold_full"], "ta")
    rest_s2_full = _split_bold(dfs["s2_bold_full"], "rest")
    ta_s2_full   = _split_bold(dfs["s2_bold_full"], "ta")

    figures = {
        "baseline_t1": plot_mriqc_boxplots(
            df_subset=dfs["s1_t1"], df_full=dfs["s1_t1_full"], metrics=t1_metrics,
            title="Baseline T1 MRIQC Metrics",
            outfile=Path(out_dir) / f"baseline_T1_MRIQC_metrics_{today}.png",
        ),
        "scan2_t1": plot_mriqc_boxplots(
            df_subset=dfs["s2_t1"], df_full=dfs["s2_t1_full"], metrics=t1_metrics,
            title="Scan 2 T1 MRIQC Metrics",
            outfile=Path(out_dir) / f"scan2_T1_MRIQC_metrics_{today}.png",
        ),
        "baseline_rest": plot_mriqc_boxplots(
            df_subset=rest_s1, df_full=rest_s1_full, metrics=bold_metrics,
            title="Baseline Rest MRIQC Metrics",
            outfile=Path(out_dir) / f"baseline_rest_MRIQC_metrics_{today}.png",
        ),
        "scan2_rest": plot_mriqc_boxplots(
            df_subset=rest_s2, df_full=rest_s2_full, metrics=bold_metrics,
            title="Scan 2 Rest MRIQC Metrics",
            outfile=Path(out_dir) / f"scan2_rest_MRIQC_metrics_{today}.png",
        ),
        "baseline_ta": plot_mriqc_boxplots(
            df_subset=ta_s1, df_full=ta_s1_full, metrics=bold_metrics,
            title="Baseline Think Aloud MRIQC Metrics",
            outfile=Path(out_dir) / f"baseline_ta_MRIQC_metrics_{today}.png",
        ),
        "scan2_ta": plot_mriqc_boxplots(
            df_subset=ta_s2, df_full=ta_s2_full, metrics=bold_metrics,
            title="Scan 2 Think Aloud MRIQC Metrics",
            outfile=Path(out_dir) / f"scan2_ta_MRIQC_metrics_{today}.png",
        ),
    }

    counts = {
        "baseline_t1": len(dfs["s1_t1"]),
        "baseline_rest": len(rest_s1),
        "baseline_ta": len(ta_s1),
        "scan2_t1": len(dfs["s2_t1"]),
        "scan2_rest": len(rest_s2),
        "scan2_ta": len(ta_s2),
    }

    return ReportArtifacts(cid_to_path=figures, counts=counts)
