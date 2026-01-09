# MRIQC Weekly Pipeline

Sarah Hennessy, shennessy@arizona.edu
last edit: Jan 9, 2026

Automates weekly QC for newly BIDSified CARE scans:

1. Run BIDS validation (via Deno + BIDS Validator)
2. Update scan presence / QC tracking (via `bids_qc_report.py`)
3. Identify scans missing MRIQC (`MRIQC == 0`)
4. Run MRIQC locally for those subjects (`run_mriqc_local.sh`)
5. Aggregate group TSVs for “this week” + full sample (`runmriqc_group_local.py`)
6. Generate summary plots and send an HTML email report with inline images

This is intended to be run **weekly** and produce a lightweight “mini-report” email.

> Notes from the script: you must have **Docker running** to run MRIQC, and email sending via `sendmail` works reliably only when connected to a UA machine (may fail on VPN). 

---

## File layout
.
├─ weekly_mriqc.py                 # main weekly orchestrator entrypoint
├─ bids_qc_report.py               # updates scan presence CSVs + missing scans report
├─ run_mriqc_local.sh              # runs MRIQC for one subject ID
├─ runmriqc_group_local.py         # aggregates MRIQC JSONs -> group TSVs
├─ mriqc_pipeline/                 # Python package (emailer, plotting, utils, etc.)
│  ├─ config.py
│  ├─ emailer.py
│  ├─ templates.py
│  ├─ plotting.py
│  ├─ group_report.py
│  ├─ bids_validator.py
│  └─ utils.py
└─ weekly_group_reports/           # outputs (TSVs + PNGs)

---

## Requirements

### System requirements

* **Docker Desktop** running (MRIQC uses containers). 
* **Deno** installed (used to run the BIDS Validator from `jsr:@bids/validator`). 
* `sendmail` available on the machine (used for outbound mail without SMTP auth). 

### Python requirements

* Python 3.9+ recommended
* `pandas`
* `matplotlib`

You can install Python deps with pip (example):

```bash
pip install pandas matplotlib
```

---

## Configuration

You will typically configure:

* BIDS dataset path (e.g., `/Volumes/achieve/CARE_Scans/bids` or `bids_testing`)
* Base pipeline folder (where derivatives/logs/reports live)
* Email recipients
---

## Optional Flags
 --yes to skip the validation prompt (only recommended if you KNOW your data are bids valid)
 --dry-run to not actually run MRIQC (check file structure/etc)
 --timeout 7200 etc.
 --skip-bids-val will skip the bids validation step (best if used with --yes prompt). 
    # This is only recommended if you've already validated your dataset (ie earlier that day)
 --email only. this doesnt do any calculations it just takes existing figures/ sheets and sends the email with them:
    # if you already have tsvs from today: python weekly_mriqc.py \
   --bids-folder /Volumes/achieve/CARE_Scans/bids_testing \
   --base-folder /Volumes/achieve/CARE_Study/9_fMRI_Analysis/Preprocessing/MRIQC/ \
   --recipients shennessy@arizona.edu \
   --email-only

   if you dont : 
   python weekly_mriqc.py \
   --bids-folder /Volumes/achieve/CARE_Scans/bids_testing \
   --base-folder /Volumes/achieve/CARE_Study/9_fMRI_Analysis/Preprocessing/MRIQC/ \
   --recipients shennessy@arizona.edu \
   --email-only --rerun-group

## Running the full weekly pipeline

I recommend you run this once a week at a scheduled time (ie Fridays at 9am).

### 0) Run master_bids.py: /Volumes/achieve/CARE_Scans/master_bids.py 

If you don't run this, nothing new will happen. The idea here is to do Bidsifying and QCing regularly. 
  See that script for instructions.

### 1) Make sure Docker is open

MRIQC will fail if Docker is not running. 

### 2) Run `weekly_mriqc.py`

Example:

```bash
python weekly_mriqc.py \
  --bids-folder /Volumes/achieve/CARE_Scans/bids\
  --base-folder /Volumes/achieve/CARE_Study/9_fMRI_Analysis/Preprocessing/MRIQC/ \
  --recipients shennessy@arizona.edu
```

What you’ll get:

* BIDS validator output saved under something like:
  `validator_outputs/bids_validator_output_YYYY-MM-DD.txt` 
* Weekly TSVs + plots in:
  `weekly_group_reports/`
* An email report (HTML) with inline images 
  (note: emails won't send from VPN or Jessktop. can only send from local computer on UA wifi)


---

## Running components individually

This pipeline is designed so you can run each part on its own.

### A) Run BIDS validation only

The script uses the Deno-based validator:

```bash
deno run -ERWN jsr:@bids/validator /path/to/bids_dataset
```

This is the same command constructed in `weekly_mriqc.py`. 

Output: validator stdout/stderr + return code, typically saved to `validator_outputs/`.

---

### B) Update scan presence / missing scans report (`bids_qc_report.py`)

This step updates the CSVs used to decide which scans still need MRIQC. In the original script it’s referenced as:

* `scan_presence_baseline_qc.csv`
* `scan_presence_scan2_qc.csv` 

Run it directly (example):

```bash
python bids_qc_report.py
```
---

### C) Run MRIQC for one subject (`run_mriqc_local.sh`)

Your pipeline runs MRIQC per subject using:

```bash
bash run_mriqc_local.sh XXXX
```

Where `XXXX` is the numeric portion of `sub-XXXX`. 

Example:

```bash
bash run_mriqc_local.sh 1111
```
---

### D) Aggregate group TSVs (`runmriqc_group_local.py`)

This script reads MRIQC derivatives (`sub-*/anat` and `sub-*/func`) and writes group TSVs for baseline and scan2, both modalities (T1w + bold).

#### Aggregate *all* available subjects

```bash
python runmriqc_group_local.py \
  --mriqc-deriv /path/to/derivatives/mriqc \
  --out-dir /path/to/weekly_group_reports
```

If `--subjects` is omitted, it discovers all subjects in derivatives. 

#### Aggregate only specific subjects (incremental weekly subset)

Because `--subjects` is `nargs="*"`, pass them as separate tokens:

```bash
python runmriqc_group_local.py \
  --mriqc-deriv /path/to/derivatives/mriqc \
  --out-dir /path/to/weekly_group_reports \
  --subjects 1111 11121 1333
```

Accepted subject labels:

* baseline: `####`
* scan2: `####1`
  (with or without `sub-`)

Optional flags:

* `--no-outliers` (do not add outlier columns)
* `--z-thresh 3.0` (outlier z threshold)

---

### E) Make plots only

The weekly report plots are generated from:

* “this week” TSVs (dated): `baseline_T1w_YYYY-MM-DD.tsv`, `scan2_bold_YYYY-MM-DD.tsv`, etc.
* full-sample TSVs (undated): `baseline_T1w.tsv`, `scan2_bold.tsv`, etc. 
---

### F) Send the email only

The email report is HTML with inline images attached via Content-ID (`cid:`). script builds a `cid_to_path` map like:

* `baseline_t1`, `scan2_t1`
* `baseline_rest`, `scan2_rest`
* `baseline_ta`, `scan2_ta` 

and sends with `send_email_inline_images(...)`. 

If you have generated the PNGs already, you can re-send the email without recomputing anything.

```bash
python weekly_mriqc.py \
  --bids-folder /path/to/bids \
  --base-folder /path/to/MRIQC/ \
  --recipients shennessy@arizona.edu \
  --email-only
```


---

## Outputs

### Validator outputs

* `validator_outputs/bids_validator_output_YYYY-MM-DD.txt` 

### Weekly group reports

In `weekly_group_reports/`:

* TSVs for “this week” (dated)
* TSVs for full sample (undated)
* PNG plots saved with date suffixes

### Logs

* Per-subject MRIQC stdout/stderr logs (if enabled in your local runner) 


---

## Troubleshooting

### Email not sending

* `sendmail` must exist (`shutil.which("sendmail")` must succeed). 
* May fail on VPN; works best connected to UA machine. Will not work on official campus machines. 

### MRIQC fails

* Confirm Docker is running. 
* Check per-subject `.err.txt` logs for that ID. 

### No “missing” subjects found

* Ensure `bids_qc_report.py` has been run recently to update the scan presence CSVs. 

### Rest / TA splits look wrong

* The pipeline filters BOLD by substring matches on `file_name` (e.g., contains `"rest"` or `"ta"`). 
 
---


