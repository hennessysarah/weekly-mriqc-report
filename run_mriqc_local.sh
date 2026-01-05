#!/bin/bash

############################################################
# MRIQC LOCAL RUN SCRIPT 
############################################################

# Path to your BIDS dataset
DATA="/PATH TO/bids"

# Path to your derivatives output directory
APP_DERIV_DIR="/PATH TO/derivatives/mriqc"

# Path to your MRIQC working directory (can delete anytime)
WORK_DIR="/PATH TO/mriqc_work"

# Subject label (e.g., 001)
Subject=$1

if [ -z "$Subject" ]; then
    echo "Usage: ./run_mriqc_local.sh <SUBJECT>"
    exit 1
fi

echo "Running MRIQC for subject sub-${Subject}"
echo "BIDS directory: $DATA"
echo "Output directory: $APP_DERIV_DIR"

# Ensure output dirs exist
mkdir -p "$APP_DERIV_DIR"
mkdir -p "$WORK_DIR"

############################################################
# Run MRIQC via Docker
############################################################

docker run --rm -it \
    -v "$DATA":/data:ro \
    -v "$APP_DERIV_DIR":/out \
    -v "$WORK_DIR":/work \
    nipreps/mriqc:23.1.0 \
    /data /out participant \
    --participant_label sub-$Subject \
    -m T1w bold \
    -w /work \
    --verbose-reports \
    --no-sub

echo "Done! Outputs saved to: $APP_DERIV_DIR"
