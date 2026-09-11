#!/bin/bash

usage() {
    echo "Usage: $0 {edca|ofdma|a2p|a2pv2|uora|cmab}[_ari][_dlfirst]"
    echo "  <mode>_ari (a2p_ari|a2pv2_ari|uora_ari|cmab_ari) sweeps the Access"
    echo "  Request Interval (params/<mode>_ari_xr_input.csv), writing to a"
    echo "  separate xr_data_ari/ root so it never collides with the baseline"
    echo "  xr_data/ sweep."
    echo "  <mode>_dlfirst (uora|cmab only) enables DlFirstAcrossAcs and writes"
    echo "  to xr_data_dlfirst/ (or xr_data_ari_dlfirst/). It reuses the input"
    echo "  CSV of the mode without the suffix, since the parameter space is"
    echo "  unchanged."
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

MODE="$1"

# The _dlfirst arm sweeps the same parameter space as its base mode, so it reads
# that mode's CSV; only the scheduler attribute and the output root differ.
PARAM_MODE="${MODE%_dlfirst}"

sbatch --nodes=33 --partition=zen2 --export=ALL,MODE="$MODE" wrapper.slurm params/${PARAM_MODE}_xr_input.csv job_script_xr.sh
