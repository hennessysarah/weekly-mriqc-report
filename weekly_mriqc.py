#weekly_mriqc.py

# This script is intended to be run *weekly* to keep an eye on quality metrics of ongoing MRI scans


# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 6, 2026

# To run: 
# 1) open docker
# 2) open terminal: pythong [drag in script]. can be run from anywhere i believe


# python weekly_mriqc.py \
#   --bids-folder /bids_testing [put actual bids folder here] \
#   --base-folder /MRIQC/ \
#   --recipients shennessy@arizona.edu

# optional flags: 
# --yes to skip the prompt
# --dry-run to not actually run MRIQC
# --timeout 7200 etc.
# -- email only. this doesnt do any calculations it just takes existing figures/ sheets and sends the email with them:
    # if you already have tsvs from today: python weekly_mriqc.py \
  # --bids-folder /bids_testing \
  # --base-folder /MRIQC/ \
  # --recipients shennessy@arizona.edu \
  # --email-only

  # if you dont : 
  # python weekly_mriqc.py \
  # --bids-folder /bids_testing \
  # --base-folder /MRIQC/ \
  # --recipients shennessy@arizona.edu \
  # --email-only --rerun-group


# this script:

# 1. runs bids validator, sends an email to the user once done to check output. Takes a y or n to continue or quit 
# 2. runs bids_qc_report.py, which updates "scan_presence_XXX.csv" and "missing_scans_report__.txt" 
#       with 1s or 0s depending on if it has been 1) collected at all 2) QCed 
# 3. Makes a list of only scans that have NOT been QCed (0s in mriqc column) 
# 4. runs them through run_mriqc_local.sh using command "bash run_mriqc_local XX"  
#       where XX is the number part of the sub-id (sub-XXXX)
# 5. aggregates QC data for only the subjects it just ran, puts the group report in weekly_group_reports folder 
# 6. emails the user with summary report (which has summary plots!)

# How does the email send work? 
# It sends locally, without requiring authorization, but ONLY if you are connected to a personal laptop WHILE ON CAMPUS
# Will not always work on VPN. 
# will not work on Jessktop because it is a campus official computer with those rights stripped away. 



from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import re
from pathlib import Path

from mriqc_pipeline.config import PipelineConfig
from mriqc_pipeline.bids_validator import validate_bids
from mriqc_pipeline.emailer import send_email_plaintext, send_email_inline_images
from mriqc_pipeline.mriqc_local import load_scan_presence, find_missing_mriqc_ids, run_mriqc_for_ids
from mriqc_pipeline.group_report import run_group_mriqc, make_weekly_figures
from mriqc_pipeline.templates import build_mriqc_email_html

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--bids-folder", type=Path, required=True)
    p.add_argument("--base-folder", type=Path, required=True)
    p.add_argument("--recipients", nargs="+", default=["shennessy@arizona.edu"])
    p.add_argument("--yes", action="store_true", help="Do not prompt to continue after BIDS validation.")
    p.add_argument("--timeout", type=int, default=None, help="Timeout seconds per MRIQC subject (optional).")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--email-only", action="store_true",
                   help="Skip validation + running MRIQC; just build group figures from existing TSVs and email them.")
    p.add_argument("--rerun-group", action="store_true",
                   help="When used with --email-only, re-run runmriqc_group_local.py before emailing.")

    return p.parse_args()

def main():
    args = parse_args()
    cfg = PipelineConfig(bids_folder=args.bids_folder, base_folder=args.base_folder)

    print("##### Hello! Welcome to the Master MRIQC Script #####")
    print("For this script to work you must have docker running!")

    if args.email_only:
        today = datetime.now().strftime("%Y-%m-%d")
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        print("in EMAIL ONLY mode. No calculations will be run. Only emails sent.")
        print("\n### MAKE SURE YOU ARE ON YOUR LOCAL COMPUTER ON UA WIFI \n emails will not send from VPN or Jessktop.")

        cfg.weekly_group_reports_dir.mkdir(parents=True, exist_ok=True)

        # optional: regenerate the TSV snapshots first
        if args.rerun_group:
            run_group_mriqc(
                script_path=cfg.runmriqc_group_script,
                deriv_dir=cfg.mriqc_derivatives_dir,
                out_dir=cfg.weekly_group_reports_dir,
                targets=[],   # empty => do NOT pass --subjects; aggregate ALL discovered
            )

        artifacts = make_weekly_figures(out_dir=cfg.weekly_group_reports_dir, today=today)

        # For email-only, use the weekly TSV counts (not targets list)
        # You can approximate "processed this week" as unknown:
        ntargets = 0
        nbaseline = 0
        nscan2 = 0

        html = build_mriqc_email_html(
            seven_days_ago=seven_days_ago,
            today=today,
            output_directory=cfg.weekly_group_reports_dir,
            ntargets=ntargets,
            nbaseline=nbaseline,
            nscan2=nscan2,
            counts=artifacts.counts,
            available_cids=set(artifacts.cid_to_path.keys()),
        )

        send_email_inline_images(
            subject=f"MRIQC Mini-Report: {seven_days_ago} – {today}",
            recipient_list=args.recipients,
            html_body=html,
            cid_to_path=artifacts.cid_to_path,
            sender=cfg.sender_email,
        )
        print("Done")
        return

    # STEP 1: BIDS VALIDATION
    result = validate_bids(bids_folder=cfg.bids_folder, output_dir=cfg.validator_outputs_dir)

    # STEP 2: Email validator output
    subject = f"[MRIQC] BIDS validation {result.status} for {cfg.bids_folder.name}"
    body = (
        f"Status: {result.status}\n"
        f"BIDS folder: {cfg.bids_folder}\n\n"
        f"Validator output saved to: {result.output_file}\n\n"
        f"===== STDOUT =====\n{result.stdout or '(no stdout)'}\n\n"
        f"===== STDERR =====\n{result.stderr or '(no stderr)'}\n"
    )
    send_email_plaintext(subject, args.recipients, body, sender=cfg.sender_email)

    if not args.yes:
        cont = input("\nContinue to MRIQC? (y/n): ").strip().lower()
        if cont != "y":
            return

    # STEP 3: Find missing MRIQC and run locally
    df = load_scan_presence([cfg.scan_presence_baseline_csv, cfg.scan_presence_scan2_csv])
    targets = find_missing_mriqc_ids(df)

    if len(targets) == 0:
        print("No subjects with MRIQC == 0 found. Nothing to run.")
        return

    summary = run_mriqc_for_ids(
        mriqc_script=cfg.mriqc_script,
        targets=targets,
        logs_dir=cfg.mriqc_logs_dir,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
    )

    # STEP 4: Group report + figures
    cfg.weekly_group_reports_dir.mkdir(parents=True, exist_ok=True)

    run_group_mriqc(
        script_path=cfg.runmriqc_group_script,
        deriv_dir=cfg.mriqc_derivatives_dir,
        out_dir=cfg.weekly_group_reports_dir,
        targets=targets,
    )

    today = datetime.now().strftime("%Y-%m-%d")
    artifacts = make_weekly_figures(out_dir=cfg.weekly_group_reports_dir, today=today)

    # STEP 5: Email report with inline images
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    nbaseline = len([t for t in targets if re.fullmatch(r"\d{4}", t)])
    nscan2 = len([t for t in targets if re.fullmatch(r"\d{4}1", t)])
    ntargets = len(targets)

    html = build_mriqc_email_html(
        seven_days_ago=seven_days_ago,
        today=today,
        output_directory=cfg.weekly_group_reports_dir,
        ntargets=ntargets,
        nbaseline=nbaseline,
        nscan2=nscan2,
        counts=artifacts.counts,
        available_cids=set(artifacts.cid_to_path.keys()),
    )

    send_email_inline_images(
        subject=f"MRIQC Mini-Report: {seven_days_ago} – {today}",
        recipient_list=args.recipients,
        html_body=html,
        cid_to_path=artifacts.cid_to_path,
        sender=cfg.sender_email,
    )

if __name__ == "__main__":
    main()
