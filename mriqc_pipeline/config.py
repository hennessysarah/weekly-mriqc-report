#config.py

# for the weekly MRIQC script, configurations

# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 4, 2026


from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)

class PipelineConfig:
    bids_folder: Path
    base_folder: Path
    sender_email: str = "shennessy@arizona.edu"

    @property
    def validator_outputs_dir(self) -> Path:
        return self.base_folder / "validator_outputs"

    @property
    def scan_presence_baseline_csv(self) -> Path:
        return self.base_folder / "scan_presence_baseline_qc.csv"

    @property
    def scan_presence_scan2_csv(self) -> Path:
        return self.base_folder / "scan_presence_scan2_qc.csv"

    @property
    def mriqc_script(self) -> Path:
        return self.base_folder / "run_mriqc_local.sh"

    @property
    def mriqc_logs_dir(self) -> Path:
        return self.base_folder / "mriqc_local_logs"

    @property
    def mriqc_derivatives_dir(self) -> Path:
        return self.base_folder / "derivatives" / "mriqc"

    @property
    def weekly_group_reports_dir(self) -> Path:
        return self.base_folder / "weekly_group_reports"

    @property
    def runmriqc_group_script(self) -> Path:
        return self.base_folder / "runmriqc_group_local.py"
