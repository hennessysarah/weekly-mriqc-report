# plotting
# for weekly mriqc script

# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 4, 2026


from __future__ import annotations
from pathlib import Path
from typing import Iterable
import matplotlib.pyplot as plt
import pandas as pd

def plot_mriqc_boxplots(
    *,
    df_subset: pd.DataFrame,
    df_full: pd.DataFrame,
    metrics: Iterable[str],
    title: str,
    outfile: Path,
    dpi: int = 300,
) -> Path:
    metrics = list(metrics)
    fig, axes = plt.subplots(1, len(metrics), figsize=(4 * len(metrics), 4), sharey=False)

    if len(metrics) == 1:
        axes = [axes]

    for ax, metric in zip(axes, metrics):
        data_subset = df_subset[metric].dropna()
        data_full = df_full[metric].dropna()

        ax.boxplot(
            [data_subset, data_full],
            positions=[1, 2],
            widths=0.6,
            patch_artist=True,
            showfliers=False,
            boxprops=dict(facecolor="lightgray"),
        )
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["This Week", "Full sample"])
        ax.set_title(metric)
        ax.set_ylabel(metric)

    fig.suptitle(title, fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.92])

    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return outfile
