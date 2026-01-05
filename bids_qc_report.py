# bids_qc_report.py

# Sarah Hennessy
# Last edit: December 27, 2025


"""
bids_qc_report.py

This script audits the completeness of BIDS-formatted MRI data and associated
MRIQC outputs for the CARE study. It generates summary tables indicating which
imaging modalities are present for each subject and whether MRIQC outputs exist.

For each subject in the BIDS directory, the script:
    • Checks for the presence of expected scan types based on filename patterns (ie, was this scan run at all?):
        - Hippocampal T2 (acq-hippo)
        - Diffusion-weighted imaging (DWI)
        - Resting-state fMRI
        - Think-Aloud task fMRI
        - Mind’s Eye task fMRI
    • Records scan presence based solely on files found in the BIDS directory
      (i.e., whether the scan was acquired and saved).
    • Independently checks whether MRIQC outputs exist for each subject using
      both TSV summaries and HTML reports.
    • Assigns an MRIQC status indicating whether T1 and/or BOLD QC outputs exist.

Subjects are grouped into baseline and follow-up (scan2) cohorts based on
subject ID patterns. For each group, the script outputs:
    1) A CSV file summarizing scan presence and MRIQC status per subject
    2) A human-readable text report listing missing scans and QC status

This script is intended for data auditing and quality-control tracking, not
for determining scan usability or quality thresholds.
"""

import os
import re
import pandas as pd
from tqdm import tqdm

# -----------------------------
# CONFIGURATION
# -----------------------------
bids_dir = "/PATH TO/bids"            

mriqc_root = "/PATH TO/MRIQC"
mriqc_group_bold = os.path.join(mriqc_root, "group_bold.tsv")
mriqc_group_t1 = os.path.join(mriqc_root, "group_T1w.tsv")
mriqc_html_dir = os.path.join(mriqc_root, "derivatives", "mriqc")

# Output file names
outputs = {
    "baseline": {
        "csv": "scan_presence_baseline_qc.csv",
        "report": "missing_scans_report_baseline_qc.txt"
    },
    "scan2": {
        "csv": "scan_presence_scan2_qc.csv",
        "report": "missing_scans_report_scan2_qc.txt"
    }
}

# Regex patterns for the scans
patterns = {
    "hippocampus": re.compile(r"acq-hippo.*_T2w\.nii\.gz$"),
    "dwi": re.compile(r".*_dwi\.nii\.gz$"),
    "resting_state": re.compile(r"task-rest.*_bold\.nii\.gz$"),
    "think_aloud": re.compile(r"task-ta.*_bold\.nii\.gz$"),
    "minds_eye": re.compile(r"task-me.*_bold\.nii\.gz$")
}

# -----------------------------
# SUBJECT GROUP DEFINITIONS
# -----------------------------
regex_baseline = re.compile(r"sub-\d{4}$")     # sub-XXXX  
regex_scan2 = re.compile(r"sub-\d{4}1$")       # sub-XXXX1  


# -----------------------------
# MRIQC PRESENCE CHECKING
# -----------------------------
def load_mriqc_tsv_subjects():
    """Load subject IDs found in MRIQC TSVs, normalizing bids_name to sub-XXXX."""
    bold_set = set()
    t1_set = set()

    def extract_sub_prefix(bids_name):
       # m = re.match(r"(sub-\d{4})", str(bids_name))
        m = re.match(r"(sub-\d{4}1?)", str(bids_name))

        return m.group(1) if m else None

    if os.path.exists(mriqc_group_bold):
        bold_df = pd.read_csv(mriqc_group_bold, sep="\t")
        for val in bold_df["bids_name"]:
            prefix = extract_sub_prefix(val)
            if prefix:
                bold_set.add(prefix)

    if os.path.exists(mriqc_group_t1):
        t1_df = pd.read_csv(mriqc_group_t1, sep="\t")
        for val in t1_df["bids_name"]:
            prefix = extract_sub_prefix(val)
            if prefix:
                t1_set.add(prefix)

    return bold_set, t1_set


def build_mriqc_html_index(mriqc_html_dir):
    """
    Return dict: sub_id -> (has_t1_html, has_bold_html)
    Lists the directory once to avoid repeated network calls.
    """
    index = {}
    try:
        for entry in os.scandir(mriqc_html_dir):
            if not entry.is_file():
                continue
            name = entry.name

            # Only care about files that look like subject HTML reports
          #  m = re.match(r"(sub-\d{4})", name)
            m = re.match(r"(sub-\d{4}1?)", str(name))

            if not m:
                continue
            sub_id = m.group(1)

            has_t1, has_bold = index.get(sub_id, (False, False))
            if "T1w.html" in name:
                has_t1 = True
            if "bold.html" in name:
                has_bold = True
            index[sub_id] = (has_t1, has_bold)

    except TimeoutError:
        # Network mount stalled: return empty index and let TSVs carry the logic
        return {}

    except OSError:
        # Covers Errno 60 sometimes surfaced as OSError
        return {}

    return index


def evaluate_mriqc_status(sub_id, bold_set, t1_set, html_index):
    """Return MRIQC status code: 1 / 'no_bold' / 'no_t1' / 0."""
    in_tsv_t1 = sub_id in t1_set
    in_tsv_bold = sub_id in bold_set

    html_t1, html_bold = html_index.get(sub_id, (False, False))

    has_t1 = in_tsv_t1 or html_t1
    has_bold = in_tsv_bold or html_bold

    if has_t1 and has_bold:
        return 1
    elif has_t1 and not has_bold:
        return "no_bold"
    elif has_bold and not has_t1:
        return "no_t1"
    else:
        return 0


# -----------------------------
# FUNCTION TO CHECK ONE SUBJECT
# -----------------------------
def check_subject(sub_path, sub_id, bold_set, t1_set, html_index):
    row = {
        "ID": sub_id,
        "hippocampus": 0,
        "dwi": 0,
        "resting_state": 0,
        "think_aloud": 0,
        "minds_eye": 0
    }

 #   Scan presence (does the scan exist in the Bids folder)
    for root, dirs, files in os.walk(sub_path):
        for f in files:
            for key, regex in patterns.items():
                if regex.search(f):
                    row[key] = 1

    # MRIQC column
   # row["MRIQC"] = evaluate_mriqc_status(sub_id, bold_set, t1_set)
    row["MRIQC"] = evaluate_mriqc_status(sub_id, bold_set, t1_set, html_index)


    return row


# -----------------------------
# MAIN PROCESSING FUNCTION
# -----------------------------
def process_group(subjects, group_name, bold_set, t1_set, html_index):
    results = []

    print(f"\nProcessing {group_name} subjects ({len(subjects)} found)...\n")

    for sub_id in tqdm(subjects, desc=f"Scanning {group_name}", ncols=80):
        sub_path = os.path.join(bids_dir, sub_id)
        row = check_subject(sub_path, sub_id, bold_set, t1_set, html_index)
        results.append(row)

    df = pd.DataFrame(results).sort_values("ID")
    df.to_csv(outputs[group_name]["csv"], index=False)

    print(f"\nSaved {group_name} scan table to: {outputs[group_name]['csv']}")

    # Missing scan report
    missing_lines = []
    missing_lines.append(f"====== Missing Scans Report ({group_name}) ======\n")

    for _, row in df.iterrows():
        missing = [m for m in patterns.keys() if row[m] == 0]

        # append MRIQC info
        if row["MRIQC"] == 1:
            mriqc_status = "MRIQC OK"
        elif row["MRIQC"] == 0:
            mriqc_status = "MRIQC missing BOTH"
        else:
            mriqc_status = f"MRIQC {row['MRIQC']}"

        if missing:
            missing_lines.append(
                f"{row['ID']} missing: {', '.join(missing)} | {mriqc_status}"
            )
        else:
            missing_lines.append(
                f"{row['ID']} has ALL scans ✓ | {mriqc_status}"
            )

    missing_lines.append("\n=================================\n")

    with open(outputs[group_name]["report"], "w") as f:
        f.write("\n".join(missing_lines))

    print(f"Missing scans report saved to: {outputs[group_name]['report']}\n")


# -----------------------------
# MAIN SCRIPT
# -----------------------------
def main():
    # Load MRIQC TSV subject sets
    bold_set, t1_set = load_mriqc_tsv_subjects()
    html_index = build_mriqc_html_index(mriqc_html_dir)


    # Identify all subject folders
    all_subjects = sorted([
        s for s in os.listdir(bids_dir)
        if s.startswith("sub-") and os.path.isdir(os.path.join(bids_dir, s))
    ])

    # Split into baseline and scan2 groups
    baseline_subjects = [s for s in all_subjects if regex_baseline.match(s)]
    scan2_subjects = [s for s in all_subjects if regex_scan2.match(s)]

    # Process each group
    #process_group(baseline_subjects, "baseline", bold_set, t1_set)
    process_group(baseline_subjects, "baseline", bold_set, t1_set, html_index)
    process_group(scan2_subjects, "scan2", bold_set, t1_set, html_index)


if __name__ == "__main__":
    main()
