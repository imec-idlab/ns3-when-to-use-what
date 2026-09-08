#!/bin/bash

usage() {
    echo "Usage: $0 {edca|ofdma|a2p|a2pv2|uora|cmab}[_ari]"
    echo "  <mode>_ari (a2p_ari|a2pv2_ari|uora_ari|cmab_ari) sweeps the Access"
    echo "  Request Interval (params/<mode>_ari_xr_input.csv), writing to a"
    echo "  separate xr_data_ari/ root so it never collides with the baseline"
    echo "  xr_data/ sweep."
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

MODE="$1"

sbatch --nodes=33 --partition=zen2 --export=ALL,MODE="$MODE" wrapper.slurm params/${MODE}_xr_input.csv job_script_xr.sh
