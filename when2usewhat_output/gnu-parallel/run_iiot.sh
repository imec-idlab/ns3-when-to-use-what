#!/bin/bash

usage() {
    echo "Usage: $0 {edca|ofdma|a2p|a2pv2|uora}"
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

MODE="$1"

if [[ "$MODE" == "uora" ]]; then
    INPUT_FILE="params/${MODE}_iiot_input.csv"
else
    INPUT_FILE="params/iiot_input.csv"
fi

sbatch --nodes=4 --partition=zen3 --export=ALL,MODE="$MODE" wrapper.slurm "$INPUT_FILE" job_script_iiot.sh
